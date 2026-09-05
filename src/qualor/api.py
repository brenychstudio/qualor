"""Minimal bootstrap API; no provider or agent initialization."""

from fastapi import FastAPI

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "qualor", "status": "ok", "phase": "bootstrap"}
