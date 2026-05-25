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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import threading

# Globally selenium Chrome
options = Options()

options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1366,768")
options.add_argument("--blink-settings=imagesEnabled=false")

options.page_load_strategy = "eager" # don't wait for every image/resource

prefs = {
    "profile.managed_default_content_settings.images": 2
}
options.add_experimental_option("prefs", prefs)

service = Service("/usr/bin/chromedriver")

# Create ONE global browser instance
driver = None
driver_lock = threading.Lock()


@app.on_event("startup")
def startup_event():
    global driver
    driver = webdriver.Chrome(service=service, options=options)


@app.on_event("shutdown")
def shutdown_event():
    global driver
    if driver:
        driver.quit()
        driver = None


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
    global driver

    if driver is None:
        raise HTTPException(status_code=503, detail="Selenium driver is not ready")

    try:
        with driver_lock:
            driver.set_page_load_timeout(timeout)
            driver.get(url)

            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.TAG_NAME, "body")
            )

            html = driver.page_source

            if not html:
                raise HTTPException(status_code=502, detail="Selenium returned empty HTML")

            return html

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL with Selenium: {str(e)}"
        )


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
