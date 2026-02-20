"""Конфигурация и загрузка данных из parse.json."""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSE_JSON_PATH = PROJECT_ROOT / "parse.json"
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
CACHE_DIR = PROJECT_ROOT / ".recorder_cache"

LIBRESPOT_CMD = os.getenv("LIBRESPOT_CMD", "librespot")
FFMPEG_CMD = os.getenv("FFMPEG_CMD", "ffmpeg")

# Spotify
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


if os.name == "nt":
    PIPE_PATH = None
else:
    PIPE_PATH = "/tmp/spotify_record_fifo"


def load_parse_json(path: Path | None = None) -> dict:
    """Загрузить данные из parse.json."""
    p = path or PARSE_JSON_PATH
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_track_by_index(data: dict, index: int) -> dict | None:
    """Получить трек по индексу (0-based)."""
    tracks = data.get("tracks") or []
    if 0 <= index < len(tracks):
        return tracks[index]
    return None


def get_track_by_uri(data: dict, uri: str) -> dict | None:
    """Получить трек по spotify_uri."""
    for t in data.get("tracks") or []:
        if t.get("spotify_uri") == uri:
            return t
    return None
