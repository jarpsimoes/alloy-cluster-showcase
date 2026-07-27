import asyncio
import logging
import os
import random
import time
from typing import Any

import psutil
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


APP_NAME = os.getenv("APP_NAME", "logs-metrics-engine")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV = os.getenv("APP_ENV", "dev")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
RANDOM_INTERVAL_SECONDS = float(os.getenv("RANDOM_INTERVAL_SECONDS", "1.5"))


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | app=%(app_name)s version=%(app_version)s env=%(app_env)s | %(message)s",
)
logger = logging.getLogger("app_logs_metrics_engine")


class AppContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.app_name = APP_NAME
        record.app_version = APP_VERSION
        record.app_env = APP_ENV
        return True


logger.addFilter(AppContextFilter())


app = FastAPI(title=APP_NAME, version=APP_VERSION)
process = psutil.Process()


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
RANDOM_EVENTS = Counter(
    "app_random_events_total",
    "Randomly generated events",
    ["level", "event_type"],
)
RANDOM_VALUE = Gauge("app_random_value", "Random gauge value to simulate app signal")
PROCESS_MEMORY_USED = Gauge("app_process_memory_used_bytes", "Process RSS memory in bytes")
SYSTEM_MEMORY_AVAILABLE = Gauge("app_system_memory_available_bytes", "System available memory in bytes")
RANDOM_OPERATION_SECONDS = Histogram(
    "app_random_operation_duration_seconds",
    "Random operation duration in seconds",
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    path = request.url.path
    method = request.method
    status = str(response.status_code)

    REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)
    return response


async def random_signal_worker(stop_event: asyncio.Event) -> None:
    event_types = ["ingest", "parse", "transform", "ship"]
    while not stop_event.is_set():
        level = random.choice(["INFO", "WARNING", "ERROR"])
        event_type = random.choice(event_types)
        value = random.uniform(0, 100)
        duration = random.uniform(0.001, 0.5)

        RANDOM_EVENTS.labels(level=level.lower(), event_type=event_type).inc()
        RANDOM_VALUE.set(value)
        RANDOM_OPERATION_SECONDS.observe(duration)

        mem = psutil.virtual_memory()
        PROCESS_MEMORY_USED.set(process.memory_info().rss)
        SYSTEM_MEMORY_AVAILABLE.set(mem.available)

        message = (
            f"random_event generated: type={event_type} value={value:.2f} "
            f"operation_seconds={duration:.4f}"
        )
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.error(message)

        await asyncio.sleep(RANDOM_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event() -> None:
    app.state.stop_event = asyncio.Event()
    app.state.bg_task = asyncio.create_task(random_signal_worker(app.state.stop_event))
    logger.info("application startup complete")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    app.state.stop_event.set()
    await app.state.bg_task
    logger.info("application shutdown complete")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "healthy"})


@app.get("/live")
async def live() -> JSONResponse:
    vm = psutil.virtual_memory()
    rss = process.memory_info().rss
    return JSONResponse(
        {
            "memory_available_bytes": vm.available,
            "memory_used_bytes": rss,
        }
    )


@app.get("/version")
async def version() -> JSONResponse:
    return JSONResponse({"name": APP_NAME, "version": APP_VERSION})


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    payload: Any = generate_latest()
    return PlainTextResponse(payload.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host=host, port=port)
