FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY config.py /app
COPY services.py /app
COPY models.py /app
COPY dbclear.py /app
COPY logging_config.py /app
COPY schemas.py /app
COPY WEB/app.py /app
COPY WEB/api_routes.py /app
COPY WEB/swagger_config.py /app
COPY WEB/static /app/static
COPY WEB/templates /app/templates
COPY alembic /app/alembic
COPY alembic.ini /app
COPY bg_class.py /app
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:5001/health || exit 1
CMD ["gunicorn", "app:app", "-w", "4", "-b", "0.0.0.0:5001"]
