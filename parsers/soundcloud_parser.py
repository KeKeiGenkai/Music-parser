import requests

def resolve_soundcloud(url, client_id):
    resolve_url = "https://api-v2.soundcloud.com/resolve"
    params = {"url": url, "client_id": client_id}
    r = requests.get(resolve_url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def parse_soundcloud_playlist(json_obj):
    if json_obj.get("kind") == "playlist":
        title = json_obj.get("title")
        tracks = []
        for t in json_obj.get("tracks", []):
            tracks.append({
                "title": t.get("title"),
                "artists": [t.get("user", {}).get("username")],
                "duration_ms": t.get("duration"),
                "permalink_url": t.get("permalink_url")
            })
        return {"source": "soundcloud", "title": title, "tracks": tracks}
    else:
        return {"source":"soundcloud","title":json_obj.get("title"), "tracks":[{
            "title": json_obj.get("title"),
            "artists":[json_obj.get("user",{}).get("username")],
            "duration_ms": json_obj.get("duration"),
            "permalink_url": json_obj.get("permalink_url")
        }]}
