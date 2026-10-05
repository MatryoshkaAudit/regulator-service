FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY regulator-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY protos /app/protos
RUN pip install --no-cache-dir -e /app/protos

COPY database /app/database
RUN pip install --no-cache-dir -e /app/database

COPY regulator-service /app/regulator-service
WORKDIR /app/regulator-service

EXPOSE 8002 50052

CMD ["python", "-m", "app.main"]
