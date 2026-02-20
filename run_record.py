#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from pathlib import Path

if sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from recorder.record import run_record_track, run_record_playlist
from recorder.config import load_parse_json, PROJECT_ROOT


def main():
    parser = argparse.ArgumentParser(
        description="Записать трек из parse.json через librespot"
    )
    parser.add_argument(
        "-i", "--index",
        type=int,
        default=0,
        help="Индекс трека в parse.json (0-based)",
    )
    parser.add_argument(
        "-p", "--parse",
        type=Path,
        default=PROJECT_ROOT / "parse.json",
        help="Путь к parse.json",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Путь для сохранения MP3",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Не вызывать API — воспроизвести трек вручную в Spotify (выбери RecordDevice)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Показать треки из parse.json и выйти",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Авторизация Spotipy (OAuth). Выполни на хосте — откроется браузер.",
    )
    parser.add_argument(
        "-t", "--track",
        type=str,
        metavar="URL",
        help="Записать один трек по ссылке (https://open.spotify.com/track/...)",
    )
    parser.add_argument(
        "--playlist",
        type=str,
        metavar="URL или путь к .json",
        help="URL плейлиста или путь к playlist.json (см. --fetch-playlist)",
    )
    parser.add_argument(
        "--fetch-playlist",
        type=str,
        metavar="URL",
        help="Скачать плейлист с API (на хосте!) и сохранить в recordings/.../playlist.json",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="С --playlist: не пропускать уже записанные треки",
    )
    args = parser.parse_args()

    if args.auth:
        from recorder.spotify_controller import get_spotify_user_client
        print("Авторизация Spotipy...")
        sp = get_spotify_user_client()
        print("Готово! Токен сохранён. Можно запускать запись.")
        return

    if args.list:
        data = load_parse_json(args.parse)
        tracks = data.get("tracks", [])
        print(f"Плейлист: {data.get('title', '?')} ({len(tracks)} треков)\n")
        for i, t in enumerate(tracks):
            artists = ", ".join(t.get("artists", []))
            title = t.get("title", "?")
            uri = t.get("spotify_uri", "")
            print(f"  [{i}] {artists} — {title}")
            print(f"      {uri}")
        return

    if args.fetch_playlist:
        from recorder.record import fetch_and_save_playlist
        path = fetch_and_save_playlist(args.fetch_playlist)
        container_path = f"/app/recordings/{path.parent.name}/playlist.json"
        print(f"Плейлист сохранён: {path}")
        print("В контейнере: python run_record.py --playlist", container_path)
        return

    if args.track:
        from recorder.spotify_controller import get_spotify_user_client
        from parsers.spotify_parser import parse_spotify_track
        sp = get_spotify_user_client()
        try:
            track_dict = parse_spotify_track(sp, args.track)
        except Exception as e:
            if "403" in str(e) or "unavailable" in str(e).lower():
                print("Ошибка: API Spotify недоступен (403 по гео). Выполни --track на хосте.")
            raise
        result = run_record_track(
            track_dict=track_dict,
            output_path=args.output,
            manual_play=args.manual,
        )
        if result is None:
            exit(1)
        return

    if args.playlist:
        recorded = run_record_playlist(
            playlist_url_or_path=args.playlist,
            manual_play=args.manual,
            skip_existing=not args.no_skip,
        )
        print(f"\nГотово: {len(recorded)} треков.")
        return

    result = run_record_track(
        track_index=args.index,
        parse_path=args.parse,
        output_path=args.output,
        manual_play=args.manual,
    )
    if result is None:
        exit(1)


if __name__ == "__main__":
    main()
