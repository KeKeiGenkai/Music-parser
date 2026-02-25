# Перенос проекта на Linux

## 1. Что скопировать на новый компьютер

Скопируй папку проекта целиком или минимум:

```
Music_Parser/
├── .env                    # Обязательно: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
├── .recorder_cache/       # Обязательно: OAuth и librespot credentials
│   ├── spotify_oauth_cache
│   ├── credentials.json   # credentials.json для librespot
│   └── ...
├── recordings/            # Опционально: уже записанные треки
├── parse.json             # Опционально
├── requirements.txt
├── web.py
├── run_record.py
├── recorder/
├── parsers/
├── recorder/Dockerfile
├── recorder/config.py
├── docker-compose.web.yml
└── ... (остальные файлы)
```

**Ключевое:** папка `.recorder_cache` содержит авторизацию. Без неё придётся заново делать `--auth` и `auth_librespot`.

---

## 2. Установка Docker на Linux

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# Выйди и зайди снова в систему (или перезагрузись)
```

**Fedora:**
```bash
sudo dnf install docker docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

**Arch:**
```bash
sudo pacman -S docker docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Проверка: `docker run hello-world`

---

## 3. Запуск сервиса

```bash
cd ~/Music_Parser   # или путь к проекту

docker compose -f docker-compose.web.yml up -d --build
```

Через 1–2 минуты веб-интерфейс будет доступен.

---

## 4. Доступ к веб-интерфейсу

- **С самого Linux:** http://localhost:8080
- **С другого устройства в сети:** http://IP_LINUX_ПК:8080  
  Узнать IP: `ip addr` или `hostname -I`

---

## 5. Если .recorder_cache пустой или потерян

### Spotipy OAuth
На Linux (или Windows с браузером):
```bash
python run_record.py --auth
```
Откроется браузер для входа в Spotify.

### librespot credentials
В контейнере:
```bash
docker exec -it spotify-record python -m recorder.auth_librespot
```
Следуй инструкциям в консоли (обычно открыть URL в браузере).

---

## 6. Переменные окружения (.env)

Убедись, что в `.env` есть:

```
SPOTIFY_CLIENT_ID=твой_client_id
SPOTIFY_CLIENT_SECRET=твой_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

`SPOTIFY_REDIRECT_URI` должен быть прописан в Spotify Dashboard (Developer) для приложения.

---

## 7. Краткая шпаргалка

| Действие          | Команда |
|-------------------|---------|
| Запуск            | `docker compose -f docker-compose.web.yml up -d` |
| Остановка         | `docker compose -f docker-compose.web.yml down` |
| Логи              | `docker compose -f docker-compose.web.yml logs -f` |
| Пересборка        | `docker compose -f docker-compose.web.yml up -d --build` |
| Вход в контейнер  | `docker exec -it spotify-record bash` |
