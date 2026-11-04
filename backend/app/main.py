"""ClearCast backend API. Interactive API docs are at /docs when it is running."""
from contextlib import asynccontextmanager
from datetime import timezone
from functools import lru_cache

import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import select, text

from app.collector import start_collector
from app.config import ML_SERVICE_URL
from app.db import Base, Prediction, SessionLocal, engine


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    stop_collector = start_collector()
    yield
    stop_collector.set()


app = FastAPI(title="ClearCast API", lifespan=lifespan)


def utc_text(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@lru_cache(maxsize=None)  # these never change while the service runs; failures aren't cached
def fetch_from_ml_service(path):
    return httpx.get(f"{ML_SERVICE_URL}{path}", timeout=30).raise_for_status().json()


def static_ml_data(path):
    try:
        return fetch_from_ml_service(path)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="The ML service is not available.")


@app.get("/api/health")
def health():
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/locations")
def locations():
    return static_ml_data("/locations")


@app.get("/api/boundaries")
def boundaries():
    return static_ml_data("/boundaries")


@app.get("/api/predictions/latest")
def latest_predictions():
    """The newest prediction per location and event, grouped by location."""
    query = (
        select(Prediction)
        .distinct(Prediction.location, Prediction.event)
        .order_by(Prediction.location, Prediction.event, Prediction.issued_at.desc())
    )
    with SessionLocal() as session:
        rows = session.scalars(query).all()

    grouped = {}
    for row in rows:
        run = grouped.setdefault(row.location, {"location": row.location, "predictions": []})
        run["predictions"].append(
            {
                "event": row.event,
                "category": row.category,
                "probability": row.probability,
                "band": row.band,
                "issued_at": utc_text(row.issued_at),
                "valid_from": utc_text(row.valid_from),
                "valid_to": utc_text(row.valid_to),
                "model_version": row.model_version,
            }
        )
    return list(grouped.values())
