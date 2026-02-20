#!/usr/bin/env python3
"""
Однократная авторизация librespot (для Docker без host network).
Сохраняет креды в .recorder_cache для последующих запусков.
"""
import subprocess
import sys
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / ".recorder_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("Авторизация librespot. Открой URL в браузере, войди в Spotify,")
    print("скопируй ПОЛНЫЙ адрес после редиректа (http://127.0.0.1:...) и вставь сюда.\n")
    cmd = [
        "librespot",
        "--name", "RecordDevice",
        "--backend", "pipe",
        "--device", "/dev/null",
        "--enable-oauth",
        "--oauth-port", "0",
        "--cache", str(CACHE_DIR),
    ]
    subprocess.run(cmd)
    return 0

if __name__ == "__main__":
    sys.exit(main())
