"""checkstock API service.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI

app = FastAPI(title="checkstock API")


@app.get("/ping")
async def ping() -> dict[str, str]:
    """Health-check / liveness endpoint (async, no thread pool)."""
    return {"status": "ok", "message": "pong"}
