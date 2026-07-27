# app-logs-metrics-engine

Small FastAPI app for logs and metrics ingestion demos.

## Features

- `GET /health` returns health JSON
- `GET /live` returns memory available and memory used JSON
- `GET /version` returns app name and version JSON
- `GET /metrics` exposes Prometheus metrics
- Background worker generates random logs and random metric signals
- App identity and behavior are configurable with environment variables

## Environment Variables

- `APP_NAME` app name shown in `/version` and logs
- `APP_VERSION` app version shown in `/version` and logs
- `APP_ENV` environment label for logs
- `HOST` bind host (default `0.0.0.0`)
- `PORT` bind port (default `8080`)
- `LOG_LEVEL` logging level (default `INFO`)
- `RANDOM_INTERVAL_SECONDS` interval between random events (default `1.5`)

## Run

```bash
cd app-logs-metrics-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export $(grep -v '^#' .env | xargs)
python app.py
```

## Test Endpoints

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8080/live
curl -s http://localhost:8080/version
curl -s http://localhost:8080/metrics | head -40
```

## Simulate multiple apps

Run several instances with different vars:

```bash
APP_NAME=orders-api APP_VERSION=2.1.0 PORT=8081 python app.py
APP_NAME=billing-api APP_VERSION=3.4.7 PORT=8082 python app.py
```
