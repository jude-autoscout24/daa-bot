FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
COPY config.example.yaml /app/config.example.yaml
COPY config.yaml /app/config.yaml
COPY README.md /app/README.md

CMD ["python", "-m", "src.main", "--config", "config.yaml", "check-once", "--store"]
