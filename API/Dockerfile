FROM python:3.13-slim
WORKDIR /api
COPY requirements.txt /api
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY config.py /api
COPY logging_config.py /api
COPY models.py /api
COPY snow.py /api
COPY API/main.py /api
COPY API/async_db.py /api
COPY API/async_cache.py /api
COPY API/async_services.py /api
COPY API/pydantic_schemas.py /api
COPY WEB/static/images/favicon.ico /api
ENV PORT=8001
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/v2/health || exit 1
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 4
