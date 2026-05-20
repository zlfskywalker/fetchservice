# External HTML Service

This service exposes cached HTML over HTTP so the Plex plugin can fetch page HTML from a local endpoint instead of scraping directly.

## Endpoints

- `GET /health`
- `GET /fetch?url=<full-url>`
- `GET /search?code=<movie-code>`
- `POST /store`

`POST /store` expects JSON:

```json
{
  "url": "https://javdb.com/search?q=ABP-123",
  "html": "<html>...</html>",
  "ttl_seconds": 21600
}
```

## Run On Raspberry Pi Without Docker

Use a 64-bit Raspberry Pi OS or Debian/Ubuntu arm64 install.

```bash
cd /opt
git clone <your-repo-url> javdb-html-cache
cd javdb-html-cache/fetch_service
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8765
```

## Run With Docker

```bash
docker build -t javdb-html-cache -f fetch_service/Dockerfile .
docker run -d \
  --name javdb-html-cache \
  -p 8765:8765 \
  -v /opt/javdb-html-cache-data:/data/cache \
  javdb-html-cache
```

## Install As A Systemd Service

```bash
sudo cp fetch_service/javdb-html-cache.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now javdb-html-cache.service
sudo systemctl status javdb-html-cache.service
```

## Plex Integration

Set `FETCH_SERVICE_URL` in `javdbAgent.py` to the service base URL, for example:

```python
FETCH_SERVICE_URL = 'http://192.168.1.50:8765'
```

The Plex plugin will then request:

- `GET /fetch?url=https%3A%2F%2Fjavdb.com%2Fsearch%3Fq%3DABP-123`
- `GET /fetch?url=https%3A%2F%2Fjavdb.com%2Fv%2Fxxxxx%3Flocale%3Dzh`
- `GET /fetch?url=https%3A%2F%2Fjavdb.com%2Factors%2Fyyyyy`
