
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_log_file = None
_quiet = False  # меньше вывода при записи плейлиста

def _log(msg: str, force: bool = False):
    line = f"[LOG] {msg}"
    if force or not _quiet:
        print(line, flush=True)
    global _log_file
    if _log_file is not None:
        try:
            _log_file.write(line + "\n")
            _log_file.flush()
        except Exception:
            pass

from .config import (
    LIBRESPOT_CMD,
    FFMPEG_CMD,
    PIPE_PATH,
    RECORDINGS_DIR,
    CACHE_DIR,
    get_track_by_index,
    load_parse_json,
)
from .spotify_controller import get_spotify_user_client, play_track_on_device, get_record_device_id
from parsers.spotify_parser import parse_spotify_playlist


def ensure_recordings_dir():
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(track: dict) -> str:
    artists = "_".join((a.replace("/", "-").replace("\\", "-")[:30] for a in track.get("artists", ["Unknown"])))
    title = (track.get("title") or "Unknown").replace("/", "-").replace("\\", "-")[:50]
    return f"{artists} - {title}"


def safe_folder_name(name: str) -> str:
    """Безопасное имя папки."""
    invalid = '<>:"/\\|?*'
    for c in invalid:
        name = name.replace(c, "_")
    return name.strip()[:100] or "playlist"


def run_record_track(
    track_index: int = 0,
    parse_path: Path | None = None,
    output_path: Path | None = None,
    manual_play: bool = False,
    track_dict: dict | None = None,
    quiet: bool = False,
) -> Path | None:
    """Записать один трек. Либо track_dict, либо (parse_path + track_index)."""
    global _log_file, _quiet
    _quiet = quiet
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RECORDINGS_DIR / "record.log"
    _log_file = open(log_path, "w", encoding="utf-8")
    _orig_stdout = sys.stdout
    class TeeOut:
        def __init__(self, f, orig): self.f, self.orig = f, orig
        def write(self, s): self.orig.write(s); self.f.write(s); self.f.flush()
        def flush(self): self.orig.flush(); self.f.flush()
    sys.stdout = TeeOut(_log_file, _orig_stdout)
    try:
        if not _quiet:
            _log(f"Лог: {log_path}")

        if platform.system() == "Windows" and "microsoft" not in platform.release().lower():
            print("[!] На Windows запись работает через WSL. Запусти скрипт в WSL:", flush=True)
            print("    wsl python run_record.py ...", flush=True)
            return None

        if track_dict is None:
            if not _quiet:
                _log("Загрузка parse.json...")
            data = load_parse_json(parse_path)
            track = get_track_by_index(data, track_index)
            if not track:
                _log(f"ОШИБКА: трек с индексом {track_index} не найден")
                return None
        else:
            track = track_dict

        uri = track.get("spotify_uri")
        duration_ms = track.get("duration_ms") or 0
        duration_sec = (duration_ms / 1000) + 3
        if not _quiet:
            _log(f"Трек: {track.get('title')} | URI: {uri} | длительность: {duration_sec:.0f} сек")

        ensure_recordings_dir()
        if output_path is None:
            base_name = safe_filename(track)
            output_path = RECORDINGS_DIR / f"{base_name}.mp3"
        else:
            output_path = Path(output_path)
        if not _quiet:
            _log(f"Выходной файл: {output_path}")

        pipe_path = PIPE_PATH
        if not pipe_path:
            pipe_path = tempfile.mktemp(prefix="spotify_fifo_", suffix="")
            try:
                os.mkfifo(pipe_path)
            except OSError:
                print("[!] mkfifo недоступен. Используй WSL.")
                return None

        if pipe_path and not os.path.exists(pipe_path):
            try:
                os.mkfifo(pipe_path)
                if not _quiet:
                    _log(f"FIFO создан: {pipe_path}")
            except OSError as e:
                _log(f"ОШИБКА создания FIFO: {e}", force=True)
                return None

        # 2. Запустить ffmpeg
        ffmpeg_cmd = [
            FFMPEG_CMD,
            "-y",
            "-f", "s16le",
            "-ar", "44100",
            "-ac", "2",
            "-i", pipe_path,
            "-t", str(int(duration_sec)),
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            str(output_path),
        ]
        if not _quiet:
            _log("Запуск ffmpeg...")
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # 3. Запустить librespot
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        use_oauth = os.environ.get("LIBRESPOT_USE_OAUTH") == "1" or Path("/.dockerenv").exists()
        librespot_cmd = [
            LIBRESPOT_CMD,
            "--name", "RecordDevice",
            "--backend", "pipe",
            "--device", pipe_path,
            "--bitrate", "320",
            "--cache", str(CACHE_DIR),
        ]
        if use_oauth:
            librespot_cmd.extend(["--enable-oauth", "--oauth-port", "0"])
        if not _quiet:
            _log("Запуск librespot...")
        librespot_proc = subprocess.Popen(
            librespot_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(5)

        if not manual_play:
            try:
                sp = get_spotify_user_client()
                device_id = get_record_device_id(sp)
                if not device_id:
                    for _ in range(6):
                        time.sleep(2)
                        device_id = get_record_device_id(sp)
                        if device_id:
                            break
                if device_id:
                    if play_track_on_device(sp, uri, device_id):
                        if not _quiet:
                            _log("Воспроизведение запущено")
                    else:
                        _log("ОШИБКА: play_track_on_device", force=True)
                else:
                    _log("RecordDevice не найден — воспроизведи вручную в Spotify", force=True)
                    manual_play = True
            except Exception as e:
                _log(f"ОШИБКА API: {e}", force=True)
                if not _quiet:
                    import traceback
                    traceback.print_exc()
                manual_play = True

        if manual_play and not _quiet:
            _log("РЕЖИМ РУЧНОЙ ИГРЫ: выбери RecordDevice и запусти трек")

        if not _quiet:
            _log(f"Ожидание {duration_sec:.0f} сек...")

        try:
            ffmpeg_proc.wait(timeout=duration_sec + 10)
        except subprocess.TimeoutExpired:
            if not _quiet:
                _log("ffmpeg timeout — остановка")
            ffmpeg_proc.kill()

        if not _quiet:
            _log("Остановка librespot...")
        librespot_proc.terminate()
        try:
            librespot_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            librespot_proc.kill()

        ffmpeg_err = ffmpeg_proc.stderr.read().decode(errors="replace") if ffmpeg_proc.stderr else ""
        librespot_err = librespot_proc.stderr.read().decode(errors="replace") if librespot_proc.stderr else ""
        if not output_path.exists() and (ffmpeg_err or librespot_err):
            _log("--- диагностика (файл не создан) ---", force=True)
            for line in (ffmpeg_err or "").strip().split("\n")[-10:]:
                _log(f"  ffmpeg: {line}", force=True)
            for line in (librespot_err or "").strip().split("\n")[-10:]:
                _log(f"  librespot: {line}", force=True)

        if pipe_path and pipe_path.startswith(tempfile.gettempdir()):
            try:
                os.remove(pipe_path)
            except OSError:
                pass

        if output_path.exists():
            if not _quiet:
                size = output_path.stat().st_size
                _log(f"ГОТОВО: {output_path} ({size} байт)")
            return output_path
        _log("ОШИБКА: файл не создан", force=True)
        return None
    finally:
        _quiet = False
        sys.stdout = _orig_stdout
        if _log_file is not None:
            try:
                _log_file.close()
            except Exception:
                pass
            _log_file = None


def fetch_and_save_playlist(playlist_url: str) -> Path:
    """Скачать плейлист через API (работает на хосте) и сохранить в recordings/Name/playlist.json."""
    sp = get_spotify_user_client()
    data = parse_spotify_playlist(sp, playlist_url)
    playlist_title = data.get("title", "playlist")
    folder_name = safe_folder_name(playlist_title)
    output_dir = RECORDINGS_DIR / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "playlist.json"
    import json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return json_path


def run_record_playlist(
    playlist_url_or_path: str,
    output_dir: Path | None = None,
    manual_play: bool = False,
    skip_existing: bool = True,
    progress_callback=None,
) -> list[Path]:
    """
    Записать все треки плейлиста. playlist_url_or_path — URL или путь к .json.
    В Docker API часто даёт 403 → используй --fetch-playlist на хосте.
    """
    path = Path(playlist_url_or_path)
    if path.suffix == ".json" and path.exists():
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    elif "spotify" in playlist_url_or_path.lower():
        try:
            sp = get_spotify_user_client()
            data = parse_spotify_playlist(sp, playlist_url_or_path)
        except Exception as e:
            if "403" in str(e) or "unavailable" in str(e).lower():
                print("Ошибка: API Spotify недоступен из контейнера (403 по гео).")
                print("На хосте выполни: python run_record.py --fetch-playlist \"URL\"")
                print("Потом в контейнере: python run_record.py --playlist recordings/ИмяПлейлиста/playlist.json")
            raise
    else:
        raise ValueError("Укажи URL плейлиста или путь к playlist.json")

    tracks = data.get("tracks", [])
    playlist_title = data.get("title", "playlist")

    folder_name = safe_folder_name(playlist_title)
    if output_dir is None:
        output_dir = RECORDINGS_DIR / folder_name
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    recorded: list[Path] = []
    total = len(tracks)

    def _report(i: int, status: str):
        if progress_callback:
            progress_callback(current=i, total=total, track=track, status=status)

    for i, track in enumerate(tracks):
        filename = safe_filename(track) + ".mp3"
        out_path = output_dir / filename
        if skip_existing and out_path.exists():
            _report(i + 1, "skip")
            if not progress_callback:
                print(f"[{i+1}/{total}] Пропуск (уже есть): {track.get('title')}")
            recorded.append(out_path)
            continue
        title_short = track.get("title", "?")
        artists_str = ", ".join(track.get("artists", []))
        if progress_callback:
            _report(i + 1, "recording")
        else:
            print(f"[{i+1}/{total}] Запись: {title_short} — {artists_str}", end=" ... ", flush=True)
        result = run_record_track(
            track_dict=track,
            output_path=out_path,
            manual_play=manual_play,
            quiet=bool(progress_callback),
        )
        if result:
            if progress_callback:
                _report(i + 1, "ok")
            else:
                print("OK")
            recorded.append(result)
        else:
            if progress_callback:
                _report(i + 1, "error")
            else:
                print("ОШИБКА")
    return recorded
