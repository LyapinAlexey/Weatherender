FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/
ENV PORT=8001
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/v2/health || exit 1
CMD uvicorn API.main:app --host 0.0.0.0 --port ${PORT} --workers 4
