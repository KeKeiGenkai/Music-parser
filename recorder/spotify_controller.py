
import os
from pathlib import Path
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

from .config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    CACHE_DIR,
)

SCOPES = [
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-private",
]
DEVICE_NAME = "RecordDevice"


def get_spotify_user_client() -> Spotify:
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError(
            "Укажи SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET в .env"
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = str(CACHE_DIR / "spotify_oauth_cache")
    in_docker = Path("/.dockerenv").exists()
    open_browser = not in_docker

    auth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=" ".join(SCOPES),
        cache_path=cache_path,
        open_browser=open_browser,
    )
    cache_file = Path(cache_path)
    if in_docker and not cache_file.exists():
        raise RuntimeError(
            "Кэш OAuth не найден! На хосте (PowerShell) выполни: python run_record.py --auth\n"
            "Откроется браузер, войди в Spotify. Потом перезапусти запись в контейнере."
        )
    token = auth.get_access_token(as_dict=False)
    if not token:
        raise RuntimeError(
            "Не удалось получить токен. На хосте выполни: python run_record.py --auth"
        )
    return Spotify(auth_manager=auth)


def get_record_device_id(sp: Spotify) -> str | None:
    try:
        resp = sp.devices()
        for d in resp.get("devices") or []:
            name = d.get("name")
            if name == DEVICE_NAME or (name and DEVICE_NAME.lower() in name.lower()):
                return d.get("id")
    except Exception:
        pass
    return None


def play_track_on_device(sp: Spotify, track_uri: str, device_id: str | None = None) -> bool:
    if not device_id:
        device_id = get_record_device_id(sp)
    if not device_id:
        return False
    try:
        sp.start_playback(device_id=device_id, uris=[track_uri])
        return True
    except Exception:
        return False


def pause_playback(sp: Spotify, device_id: str | None = None) -> bool:
    try:
        sp.pause_playback(device_id=device_id)
        return True
    except Exception:
        return False
