FROM python:3.13-slim
WORKDIR /main
COPY requirements.txt /main
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py /main
COPY services.py /main
COPY models.py /main
COPY dbclear.py /main
COPY logging_config.py /main
COPY schemas.py /main
COPY CLI/main.py /main
COPY alembic /main/alembic
COPY alembic.ini /main
COPY cache.py /main
COPY snow.py /main
CMD ["python", "main.py"]
