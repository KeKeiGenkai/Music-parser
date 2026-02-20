#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-интерфейс для записи треков Spotify.
Запуск: uvicorn web:app --host 0.0.0.0 --port 8080
"""

import re
import tempfile
import threading
import zipfile
from pathlib import Path
from urllib.parse import unquote

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse

from recorder.config import RECORDINGS_DIR
from recorder.record import (
    run_record_playlist,
    run_record_track,
    fetch_and_save_playlist,
    safe_folder_name,
)
from parsers.spotify_parser import parse_spotify_track
from recorder.spotify_controller import get_spotify_user_client

app = FastAPI(title="Spotify Recorder")

# Состояние записи (для polling)
_recording_state = {
    "running": False,
    "type": None,  # "track" | "playlist"
    "current": 0,
    "total": 0,
    "track": "",
    "artists": "",
    "status": "",  # skip | recording | ok | error
    "error": None,
    "playlist_name": "",
}
_state_lock = threading.Lock()


def _is_spotify_url(s: str) -> bool:
    return bool(s) and "spotify" in s.lower()


def _extract_type(url: str) -> str:
    if "/track/" in url:
        return "track"
    if "/playlist/" in url:
        return "playlist"
    return "unknown"


@app.get("/", response_class=HTMLResponse)
async def index():
    return _HTML_PAGE


@app.post("/api/fetch")
async def api_fetch(url: str = Query(..., description="Spotify playlist URL")):
    """Скачать метаданные плейлиста (работает на хосте, при 403 в Docker)."""
    if not _is_spotify_url(url) or _extract_type(url) != "playlist":
        raise HTTPException(400, "Укажи ссылку на плейлист Spotify")
    try:
        path = fetch_and_save_playlist(url)
        folder = path.parent.name
        return {"ok": True, "path": str(path), "folder": folder}
    except Exception as e:
        err = str(e)
        if "403" in err or "unavailable" in err.lower():
            raise HTTPException(403, "Spotify API недоступен (гео). Запусти на хосте.")
        raise HTTPException(500, err)


@app.post("/api/record")
async def api_record(url: str = Query(..., description="Spotify track or playlist URL")):
    """Запустить запись трека или плейлиста."""
    if not url or not url.strip():
        raise HTTPException(400, "Укажи ссылку на трек или плейлист Spotify")

    url = url.strip()
    if not _is_spotify_url(url):
        raise HTTPException(400, "Неверная ссылка Spotify")

    with _state_lock:
        if _recording_state["running"]:
            raise HTTPException(409, "Запись уже выполняется")

    t = _extract_type(url)
    if t == "track":

        def _do_track():
            try:
                with _state_lock:
                    _recording_state["running"] = True
                    _recording_state["type"] = "track"
                    _recording_state["current"] = 1
                    _recording_state["total"] = 1
                    _recording_state["error"] = None
                sp = get_spotify_user_client()
                track_dict = parse_spotify_track(sp, url)
                with _state_lock:
                    _recording_state["track"] = track_dict.get("title", "?")
                    _recording_state["artists"] = ", ".join(track_dict.get("artists", []))
                    _recording_state["status"] = "recording"
                run_record_track(track_dict=track_dict, manual_play=False, quiet=True)
                with _state_lock:
                    _recording_state["status"] = "ok"
            except Exception as e:
                with _state_lock:
                    _recording_state["error"] = str(e)
                    _recording_state["status"] = "error"
            finally:
                with _state_lock:
                    _recording_state["running"] = False

        thread = threading.Thread(target=_do_track, daemon=True)
        thread.start()
        return {"ok": True, "type": "track"}

    if t == "playlist":

        def _do_playlist():
            def on_progress(current, total, track, status):
                with _state_lock:
                    _recording_state["current"] = current
                    _recording_state["total"] = total
                    _recording_state["track"] = track.get("title", "?")
                    _recording_state["artists"] = ", ".join(track.get("artists", []))
                    _recording_state["status"] = status

            try:
                with _state_lock:
                    _recording_state["running"] = True
                    _recording_state["type"] = "playlist"
                    _recording_state["error"] = None
                recorded = run_record_playlist(
                    playlist_url_or_path=url,
                    manual_play=False,
                    skip_existing=True,
                    progress_callback=on_progress,
                )
                with _state_lock:
                    _recording_state["playlist_name"] = ""
            except Exception as e:
                with _state_lock:
                    _recording_state["error"] = str(e)
                    _recording_state["status"] = "error"
            finally:
                with _state_lock:
                    _recording_state["running"] = False

        thread = threading.Thread(target=_do_playlist, daemon=True)
        thread.start()
        return {"ok": True, "type": "playlist"}

    raise HTTPException(400, "Поддерживаются только треки и плейлисты")


@app.post("/api/record/json")
async def api_record_json(path: str = Query(..., description="Folder name or path to playlist.json")):
    """Записать плейлист из сохранённого JSON (обход 403). Можно указать имя папки."""
    if "/" not in path and "\\" not in path:
        p = RECORDINGS_DIR / path / "playlist.json"
    else:
        p = Path(path)
        if not p.is_absolute():
            p = RECORDINGS_DIR / path
    if not p.exists() or p.suffix != ".json":
        raise HTTPException(400, f"Файл не найден: {path}")

    with _state_lock:
        if _recording_state["running"]:
            raise HTTPException(409, "Запись уже выполняется")

    def _do():
        def on_progress(current, total, track, status):
            with _state_lock:
                _recording_state["current"] = current
                _recording_state["total"] = total
                _recording_state["track"] = track.get("title", "?")
                _recording_state["artists"] = ", ".join(track.get("artists", []))
                _recording_state["status"] = status

        try:
            with _state_lock:
                _recording_state["running"] = True
                _recording_state["type"] = "playlist"
            run_record_playlist(
                playlist_url_or_path=str(p),
                manual_play=False,
                skip_existing=True,
                progress_callback=on_progress,
            )
        except Exception as e:
            with _state_lock:
                _recording_state["error"] = str(e)
        finally:
            with _state_lock:
                _recording_state["running"] = False

    threading.Thread(target=_do, daemon=True).start()
    return {"ok": True, "type": "playlist"}


@app.get("/api/status")
async def api_status():
    with _state_lock:
        return dict(_recording_state)


@app.get("/api/playlists")
async def api_playlists():
    """Плейлисты, сохранённые через fetch (для записи при 403)."""
    if not RECORDINGS_DIR.exists():
        return {"playlists": []}
    playlists = []
    for p in sorted(RECORDINGS_DIR.iterdir()):
        if p.is_dir() and (p / "playlist.json").exists():
            playlists.append(p.name)
    return {"playlists": playlists}


@app.get("/api/recordings")
async def api_recordings():
    """Список папок и файлов в recordings."""
    if not RECORDINGS_DIR.exists():
        return {"folders": [], "files": []}
    folders = []
    root_files = []
    for p in sorted(RECORDINGS_DIR.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            tracks = [f.name for f in p.iterdir() if f.suffix == ".mp3"]
            folders.append({"name": p.name, "tracks": tracks})
        elif p.suffix == ".mp3":
            root_files.append(p.name)
    return {"folders": folders, "root_files": root_files}


def _cleanup_temp(path: str):
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


@app.get("/api/download-folder/{folder}")
async def api_download_folder(folder: str, bg: BackgroundTasks):
    """Скачать все треки папки одним ZIP-архивом."""
    folder = unquote(folder)
    if re.search(r'[<>:"/\\|?*]', folder):
        raise HTTPException(400, "Неверный путь")
    dir_path = RECORDINGS_DIR / folder
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(404, "Папка не найдена")
    mp3_files = [f for f in dir_path.iterdir() if f.is_file() and f.suffix == ".mp3"]
    if not mp3_files:
        raise HTTPException(404, "Нет MP3 в папке")
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in mp3_files:
                zf.write(f, f.name)
        tmp.close()
        bg.add_task(_cleanup_temp, tmp.name)
        return FileResponse(
            tmp.name,
            filename=f"{folder}.zip",
            media_type="application/zip",
        )
    except Exception:
        _cleanup_temp(tmp.name)
        raise


@app.get("/api/download/{folder}/{filename}")
async def api_download(folder: str, filename: str):
    """Скачать MP3."""
    folder = unquote(folder)
    filename = unquote(filename)
    if re.search(r'[<>:"/\\|?*]', folder + filename):
        raise HTTPException(400, "Неверный путь")
    path = RECORDINGS_DIR / folder / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path, filename=filename, media_type="audio/mpeg")


@app.get("/api/download/{filename}")
async def api_download_root(filename: str):
    """Скачать MP3 из корня recordings."""
    filename = unquote(filename)
    if re.search(r'[<>:"/\\|?*]', filename):
        raise HTTPException(400, "Неверный путь")
    path = RECORDINGS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path, filename=filename, media_type="audio/mpeg")


_HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Spotify Recorder</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 2rem; background: #0d1117; color: #e6edf3; }
        h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }
        .input-row { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
        input[type="text"] { flex: 1; padding: 0.6rem 1rem; border: 1px solid #30363d; border-radius: 6px; background: #161b22; color: #e6edf3; font-size: 1rem; }
        button { padding: 0.6rem 1.2rem; border: none; border-radius: 6px; background: #238636; color: white; font-weight: 600; cursor: pointer; font-size: 1rem; }
        button:hover { background: #2ea043; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .progress { margin: 1.5rem 0; padding: 1rem; background: #161b22; border-radius: 8px; border: 1px solid #30363d; }
        .progress.hidden { display: none; }
        .progress-label { color: #8b949e; font-size: 0.9rem; margin-bottom: 0.5rem; }
        .progress-bar { height: 8px; background: #21262d; border-radius: 4px; overflow: hidden; margin: 0.5rem 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #238636, #2ea043); transition: width 0.3s; }
        .track-info { font-size: 1rem; margin-top: 0.5rem; }
        .error { color: #f85149; margin-top: 0.5rem; }
        .recordings { margin-top: 2rem; }
        .recordings h2 { font-size: 1.1rem; margin-bottom: 1rem; }
        .folder { margin-bottom: 1.5rem; }
        .folder-name { font-weight: 600; margin-bottom: 0.5rem; color: #58a6ff; display: flex; align-items: center; gap: 0.75rem; }
        .dl-all { font-size: 0.85rem; font-weight: normal; padding: 0.25rem 0.6rem; background: #21262d; border-radius: 6px; color: #58a6ff; text-decoration: none; }
        .dl-all:hover { background: #30363d; }
        .track { padding: 0.4rem 0; border-bottom: 1px solid #21262d; display: flex; justify-content: space-between; align-items: center; }
        .track a { color: #58a6ff; text-decoration: none; }
        .track a:hover { text-decoration: underline; }
        .status-msg { margin-top: 0.5rem; font-size: 0.9rem; }
    </style>
</head>
<body>
    <h1>Spotify Recorder</h1>
    <p style="color: #8b949e; margin-bottom: 1.5rem;">Вставь ссылку на трек или плейлист — файлы сохранятся и будут доступны для скачивания.</p>

    <div class="input-row">
        <input type="text" id="url" placeholder="https://open.spotify.com/track/... или /playlist/..." autocomplete="off">
        <button id="btn" onclick="startRecord()">Записать</button>
    </div>
    <details class="details-403" style="margin-top:1rem;">
        <summary style="cursor:pointer;color:#8b949e;font-size:0.9rem;">При 403: записать сохранённый плейлист</summary>
        <div style="margin-top:0.5rem;display:flex;gap:0.5rem;align-items:center;">
            <select id="playlistSelect" style="padding:0.4rem;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;min-width:200px;"></select>
            <button id="btnJson" onclick="startRecordJson()">Записать</button>
        </div>
        <p style="color:#8b949e;font-size:0.85rem;margin-top:0.5rem;">Сначала на хосте: <code>python run_record.py --fetch-playlist "URL"</code></p>
    </details>

    <div id="progress" class="progress hidden">
        <div class="progress-label">Запись...</div>
        <div class="progress-bar"><div id="progressFill" class="progress-fill" style="width: 0%"></div></div>
        <div id="trackInfo" class="track-info"></div>
        <div id="error" class="error"></div>
    </div>

    <div class="recordings">
        <h2>Записи</h2>
        <div id="recordingsList"></div>
    </div>

    <script>
        const urlInput = document.getElementById('url');
        const btn = document.getElementById('btn');
        const progress = document.getElementById('progress');
        const progressFill = document.getElementById('progressFill');
        const trackInfo = document.getElementById('trackInfo');
        const errorEl = document.getElementById('error');

        function setProgress(running, current, total, track, artists, status, err) {
            if (running) {
                progress.classList.remove('hidden');
                const pct = total ? (current / total * 100) : 0;
                progressFill.style.width = pct + '%';
                trackInfo.textContent = track ? `${track}${artists ? ' — ' + artists : ''}` : '';
                if (status === 'skip') trackInfo.textContent += ' (пропуск)';
                else if (status === 'recording') trackInfo.textContent += ' ...';
                else if (status === 'ok') trackInfo.textContent += ' ✓';
                else if (status === 'error') trackInfo.textContent += ' ✗';
                errorEl.textContent = err || '';
            } else {
                progress.classList.add('hidden');
                errorEl.textContent = err || '';
            }
        }

        async function pollStatus() {
            const r = await fetch('/api/status');
            const s = await r.json();
            setProgress(s.running, s.current, s.total, s.track, s.artists, s.status, s.error);
            return s.running;
        }

        let pollTimer = null;
        function startPolling() {
            if (pollTimer) return;
            pollTimer = setInterval(async () => {
                const running = await pollStatus();
                if (!running) {
                    clearInterval(pollTimer);
                    pollTimer = null;
                    btn.disabled = false;
                    document.getElementById('btnJson').disabled = false;
                    loadRecordings();
                }
            }, 800);
        }

        async function startRecordJson() {
            const sel = document.getElementById('playlistSelect');
            const folder = sel.value;
            if (!folder) { errorEl.textContent = 'Выбери плейлист'; return; }
            btn.disabled = true;
            document.getElementById('btnJson').disabled = true;
            errorEl.textContent = '';
            try {
                const r = await fetch('/api/record/json?path=' + encodeURIComponent(folder), { method: 'POST' });
                const d = await r.json();
                if (!r.ok) throw new Error(d.detail || 'Ошибка');
                setProgress(true, 0, 1, 'Запуск...', '', '', '');
                startPolling();
            } catch (e) {
                errorEl.textContent = e.message;
            }
            btn.disabled = false;
            document.getElementById('btnJson').disabled = false;
        }

        async function loadPlaylists() {
            const r = await fetch('/api/playlists');
            const d = await r.json();
            const sel = document.getElementById('playlistSelect');
            sel.innerHTML = '<option value="">— выбери —</option>';
            d.playlists.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = p; sel.appendChild(o); });
        }

        async function startRecord() {
            const url = urlInput.value.trim();
            if (!url) return;
            btn.disabled = true;
            errorEl.textContent = '';
            try {
                const r = await fetch('/api/record?url=' + encodeURIComponent(url), { method: 'POST' });
                const d = await r.json();
                if (!r.ok) throw new Error(d.detail || 'Ошибка');
                setProgress(true, 0, 1, 'Запуск...', '', '', '');
                startPolling();
            } catch (e) {
                errorEl.textContent = e.message;
                btn.disabled = false;
            }
        }

        async function loadRecordings() {
            const r = await fetch('/api/recordings');
            const d = await r.json();
            let html = '';
            for (const f of d.folders) {
                html += '<div class="folder"><div class="folder-name">' + escapeHtml(f.name);
                if (f.tracks.length > 0) {
                    html += '<a href="/api/download-folder/' + encodeURIComponent(f.name) + '" class="dl-all" download>Скачать всё ZIP</a>';
                }
                html += '</div>';
                for (const t of f.tracks) {
                    html += '<div class="track"><span>' + escapeHtml(t) + '</span>';
                    html += '<a href="/api/download/' + encodeURIComponent(f.name) + '/' + encodeURIComponent(t) + '" download>Скачать</a></div>';
                }
                html += '</div>';
            }
            for (const t of d.root_files) {
                html += '<div class="track"><span>' + escapeHtml(t) + '</span>';
                html += '<a href="/api/download/' + encodeURIComponent(t) + '" download>Скачать</a></div>';
            }
            document.getElementById('recordingsList').innerHTML = html || '<p style="color:#8b949e">Нет записей</p>';
        }

        function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

        pollStatus().then(() => { if (!document.hidden) { loadRecordings(); loadPlaylists(); } });
        loadRecordings();
        loadPlaylists();
    </script>
</body>
</html>
"""
