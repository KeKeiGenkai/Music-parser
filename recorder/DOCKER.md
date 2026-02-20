# Запись через Docker (без WSL/Ubuntu)

## Что нужно

- **Docker Desktop** для Windows: [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
- **Spotify Premium**
- Файлы **`.env`** и **`parse.json`** в корне проекта

---

## Шаг 1: Собрать образ

В корне проекта (PowerShell или cmd):

```powershell
cd E:\PythonYabuchi\Music_Parser
docker compose -f docker-compose.record.windows.yml build
```

---

## Шаг 2: OAuth для Spotipy

**Один раз на хосте** — открой браузер и авторизуйся:

```powershell
cd E:\PythonYabuchi\Music_Parser
python run_record.py --auth
```

При первом запуске откроется браузер. Войди в Spotify, разреши доступ. Токен сохранится в `.recorder_cache/spotify_oauth_cache`.

---

## Шаг 3: OAuth для librespot (в контейнере)

Только для Windows (без host network). Один раз:

```powershell
docker compose -f docker-compose.record.windows.yml run --rm --entrypoint "python3" record recorder/auth_librespot.py
```

1. Появится URL — открой его в браузере
2. Войди в Spotify
3. После редиректа скопируй **весь** адрес из строки браузера (`http://127.0.0.1/login?code=...`)
4. Вставь в терминал и нажми Enter

Креды сохранятся в `.recorder_cache/`.

---

## Шаг 4: Запустить контейнер и войти в него

```powershell
# Запустить контейнер (будет работать в фоне)
docker compose -f docker-compose.record.windows.yml up -d

# Войти в консоль контейнера
docker exec -it spotify-record bash
```

Либо в **Docker Desktop**: списки контейнеров → **spotify-record** → кнопка **Terminal** (или правый клик → Open in terminal).

---

## Шаг 5: Команды внутри контейнера

В терминале контейнера:

```bash
# Список треков
python run_record.py --list

# Записать первый трек
python run_record.py --index 0

# Записать второй трек
python run_record.py --index 1
```

MP3 появятся в папке `recordings/` на хосте.

Выход из консоли: `exit`

---

## На Linux

Можно использовать `docker-compose.record.yml` (с `network_mode: host`) — тогда **Discovery** работает и шаг 3 (librespot OAuth) не нужен. Устройство RecordDevice будет видно в приложении Spotify.

---

## Если что-то не так

- **«RecordDevice не найден»** — выполни шаг 3 (librespot OAuth)
- **Ошибка OAuth** — добавь `http://127.0.0.1:8888/callback` в Spotify Dashboard → Redirect URIs
- **Нет parse.json** — создай его через API (`GET /parse?url=...`) или вручную
