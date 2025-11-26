
import os
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
from parsers.spotify_parser import get_spotify_client, parse_spotify_playlist
from parsers.soundcloud_parser import resolve_soundcloud, parse_soundcloud_playlist
import requests

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SOUNDCLOUD_CLIENT_ID = os.getenv("SOUNDCLOUD_CLIENT_ID")

app = FastAPI(title="Music Parser API")

@app.get("/parse")
async def parse(url: str = Query(..., description="Link to playlist/album/track")):
    url_l = url.lower()
    try:
        if "spotify.com" in url_l:
            if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
                raise HTTPException(status_code=500, detail="Spotify credentials not set")
            sp = get_spotify_client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            result = parse_spotify_playlist(sp, url)
            return result

        if "soundcloud.com" in url_l:
            if not SOUNDCLOUD_CLIENT_ID:
                raise HTTPException(status_code=500, detail="SoundCloud client_id not set")
            json_obj = resolve_soundcloud(url, SOUNDCLOUD_CLIENT_ID)
            return parse_soundcloud_playlist(json_obj)

        raise HTTPException(status_code=400, detail="Unsupported platform / invalid url")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
