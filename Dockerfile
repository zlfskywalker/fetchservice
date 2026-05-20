FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HTML_CACHE_DIR=/data/cache
ENV HTML_CACHE_TTL_SECONDS=21600

WORKDIR /app

COPY fetch_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY fetch_service /app

VOLUME ["/data/cache"]
EXPOSE 8765

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8765"]
