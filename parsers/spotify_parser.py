from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

def get_spotify_client(client_id, client_secret):
    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    return Spotify(auth_manager=auth)

def fetch_all_spotify_tracks(sp, playlist_id):
    tracks = []
    limit = 100
    offset = 0

    while True:
        response = sp.playlist_items(
            playlist_id,
            limit=limit,
            offset=offset
        )

        for item in response.get("items", []):
            t = item.get("track") or {}
            tracks.append({
                "title": t.get("name"),
                "artists": [a.get("name") for a in t.get("artists", [])],
                "album": t.get("album", {}).get("name"),
                "duration_ms": t.get("duration_ms"),
                "spotify_uri": t.get("uri"),
                "spotify_id": t.get("id")
            })

        if response.get("next") is None:
            break

        offset += limit

    return tracks

def parse_spotify_playlist(sp, url_or_id):
    if "spotify" in url_or_id:
        playlist_id = url_or_id.rstrip('/').split("/")[-1].split("?")[0]
    else:
        playlist_id = url_or_id

    playlist = sp.playlist(playlist_id)

    title = playlist.get("name")
    owner = playlist.get("owner", {}).get("display_name")

    tracks = fetch_all_spotify_tracks(sp, playlist_id)

    return {
        "source": "spotify",
        "title": title,
        "owner": owner,
        "tracks": tracks
    }
