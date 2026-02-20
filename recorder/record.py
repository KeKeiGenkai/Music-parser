
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_log_file = None

def _log(msg: str):
    line = f"[LOG] {msg}"
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


def ensure_recordings_dir():
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(track: dict) -> str:
    artists = "_".join((a.replace("/", "-").replace("\\", "-")[:30] for a in track.get("artists", ["Unknown"])))
    title = (track.get("title") or "Unknown").replace("/", "-").replace("\\", "-")[:50]
    return f"{artists} - {title}"


def run_record_track(
    track_index: int = 0,
    parse_path: Path | None = None,
    output_path: Path | None = None,
    manual_play: bool = False,
) -> Path | None:
    global _log_file
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
        _log(f"Лог: {log_path}")
        _log("Старт записи")
        _log(f"Платформа: {platform.system()}, release: {platform.release()}")

        if platform.system() == "Windows" and "microsoft" not in platform.release().lower():
            print("[!] На Windows запись работает через WSL. Запусти скрипт в WSL:", flush=True)
            print("    wsl python run_record.py ...", flush=True)
            return None

        _log("Загрузка parse.json...")
        data = load_parse_json(parse_path)
        track = get_track_by_index(data, track_index)
        if not track:
            _log(f"ОШИБКА: трек с индексом {track_index} не найден")
            return None

        uri = track.get("spotify_uri")
        duration_ms = track.get("duration_ms") or 0
        duration_sec = (duration_ms / 1000) + 3
        _log(f"Трек: {track.get('title')} | URI: {uri} | длительность: {duration_sec:.0f} сек")

        ensure_recordings_dir()
        if output_path is None:
            base_name = safe_filename(track)
            output_path = RECORDINGS_DIR / f"{base_name}.mp3"
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
                _log(f"FIFO создан: {pipe_path}")
            except OSError as e:
                _log(f"ОШИБКА создания FIFO: {e}")
                return None
        else:
            _log(f"FIFO: {pipe_path}")

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
        _log("Запуск ffmpeg...")
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _log(f"ffmpeg PID: {ffmpeg_proc.pid}")

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
        _log(f"Запуск librespot: {' '.join(librespot_cmd)}")
        librespot_proc = subprocess.Popen(
            librespot_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _log(f"librespot PID: {librespot_proc.pid}")

        _log("Ожидание 5 сек (librespot подключение к Spotify)...")
        time.sleep(5)

        if not manual_play:
            try:
                _log("Получение Spotipy клиента...")
                sp = get_spotify_user_client()
                _log("Поиск устройства RecordDevice...")
                device_id = get_record_device_id(sp)
                if device_id:
                    _log(f"Устройство найдено: {device_id}")
                    if play_track_on_device(sp, uri, device_id):
                        _log(f"Воспроизведение запущено: {track.get('title')}")
                    else:
                        _log("ОШИБКА: play_track_on_device вернул False")
                else:
                    _log("ОШИБКА: RecordDevice не найден в списке устройств Spotify")
                    _log("Воспроизведи трек вручную в Spotify → RecordDevice")
                    manual_play = True
            except Exception as e:
                _log(f"ОШИБКА API: {e}")
                import traceback
                traceback.print_exc()
                manual_play = True

        if manual_play:
            _log("РЕЖИМ РУЧНОЙ ИГРЫ: выбери RecordDevice в Spotify и запусти трек!")

        _log(f"Ожидание ffmpeg ({duration_sec:.0f} сек)...")

        try:
            ffmpeg_proc.wait(timeout=duration_sec + 10)
            _log("ffmpeg завершился")
        except subprocess.TimeoutExpired:
            _log("ffmpeg timeout — принудительная остановка")
            ffmpeg_proc.kill()

        _log("Остановка librespot...")
        librespot_proc.terminate()
        try:
            librespot_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            librespot_proc.kill()

        ffmpeg_err = ffmpeg_proc.stderr.read().decode(errors="replace") if ffmpeg_proc.stderr else ""
        librespot_err = librespot_proc.stderr.read().decode(errors="replace") if librespot_proc.stderr else ""
        if ffmpeg_err:
            _log("--- ffmpeg stderr ---")
            for line in ffmpeg_err.strip().split("\n")[-20:]:
                _log(f"  {line}")
        if librespot_err:
            _log("--- librespot stderr (последние строки) ---")
            for line in librespot_err.strip().split("\n")[-15:]:
                _log(f"  {line}")

        if pipe_path and pipe_path.startswith(tempfile.gettempdir()):
            try:
                os.remove(pipe_path)
            except OSError:
                pass

        if output_path.exists():
            size = output_path.stat().st_size
            _log(f"ГОТОВО: {output_path} ({size} байт)")
            return output_path
        _log("ОШИБКА: файл не создан. Проверь логи выше.")
        return None
    finally:
        sys.stdout = _orig_stdout
        if _log_file is not None:
            try:
                _log_file.close()
            except Exception:
                pass
            _log_file = None
