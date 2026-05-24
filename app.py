import hashlib
import json
import os
import time
from typing import Optional
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


BASE_URL = 'https://javdb.com'
SEARCH_URL = BASE_URL + '/search?q=%s'
CACHE_DIR = os.environ.get('HTML_CACHE_DIR', './cache')
DEFAULT_TTL_SECONDS = int(os.environ.get('HTML_CACHE_TTL_SECONDS', '21600'))


class StoreRequest(BaseModel):
    url: str
    html: str
    ttl_seconds: Optional[int] = None


app = FastAPI(title='JAVDB HTML Cache Service')


def ensure_cache_dir():
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def url_to_cache_path(url):
    digest = hashlib.sha256(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, digest + '.json')


def load_cached_html(url):
    path = url_to_cache_path(url)
    if not os.path.exists(path):
        return None

    with open(path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)

    expires_at = payload.get('expires_at', 0)
    if expires_at and time.time() > expires_at:
        return None

    return payload.get('html')


def store_cached_html(url, html, ttl_seconds=None):
    ensure_cache_dir()
    ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS

    payload = {
        'url': url,
        'html': html,
        'stored_at': int(time.time()),
        'expires_at': int(time.time()) + ttl if ttl > 0 else 0,
    }

    with open(url_to_cache_path(url), 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)


def get_html_with_selenium(url: str, timeout: int = 30) -> str:
    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")

    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    # Raspberry Pi path is usually this:
    service = Service("/usr/bin/chromedriver")

    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(timeout)

        driver.get(url)

        # Wait a little for JavaScript-rendered content
        time.sleep(3)

        html = driver.page_source

        if not html:
            raise HTTPException(
                status_code=502,
                detail="Selenium returned empty HTML"
            )

        return html

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL with Selenium: {str(e)}"
        )

    finally:
        if driver:
            driver.quit()


def get_or_fetch_html(url: str) -> str:
    html = load_cached_html(url)

    if html is not None:
        return html

    html = get_html_with_selenium(url)

    store_cached_html(url, html)

    return html


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/fetch', response_class=HTMLResponse)
def fetch(url: str):
    html = get_or_fetch_html(url)
    return HTMLResponse(content=html, media_type='text/html')


@app.get('/search', response_class=HTMLResponse)
def search(code: str):
    code = code.strip().upper()
    url = SEARCH_URL % quote_plus(code)

    html = get_or_fetch_html(url)

    return HTMLResponse(content=html, media_type='text/html')


@app.post('/store')
def store(payload: StoreRequest):
    store_cached_html(payload.url, payload.html, payload.ttl_seconds)
    return {'status': 'stored', 'url': payload.url}
