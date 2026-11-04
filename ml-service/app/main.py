"""ClearCast ML service. Interactive API docs are at /docs when it is running.

Run from the ml-service folder:
    uvicorn app.main:app --port 8001
"""
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.history import fetch_history
from app.locations import LOCATIONS
from app.predictor import NotEnoughData, load_bundle, predict_run

BOUNDARIES = Path(__file__).resolve().parent / "nairobi_constituencies.geojson"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


@asynccontextmanager
async def lifespan(app):
    load_bundle()  # fail at startup, not on the first request, if the models can't load
    yield


app = FastAPI(title="ClearCast ML service", lifespan=lifespan)


class Reading(BaseModel):
    """One hour of weather. A field can be empty if the source didn't report it."""

    timestamp: datetime  # on the hour; UTC is assumed if no time zone is given
    temperature: float | None = None  # degC
    humidity: float | None = None  # %
    pressure: float | None = None  # hPa at sea level
    wind_speed: float | None = None  # m/s
    wind_deg: float | None = None  # degrees
    wind_gust: float | None = None  # m/s
    rainfall: float | None = None  # mm in the preceding hour
    cloud_cover: float | None = None  # %


class PredictRequest(BaseModel):
    location: str
    readings: list[Reading]


def run_prediction(location, records):
    try:
        return predict_run(location, records)
    except NotEnoughData as e:
        raise HTTPException(status_code=422, detail=str(e))


def find_location(name):
    if name not in LOCATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown location: {name}")
    return LOCATIONS[name]


@app.get("/health")
def health():
    return {"status": "ok", "model_version": load_bundle()["version"]}


@app.get("/locations")
def locations():
    return list(LOCATIONS.values())


@app.get("/boundaries")
def boundaries():
    """Nairobi constituency boundaries as GeoJSON, for the map."""
    return json.loads(BOUNDARIES.read_text())


@app.get("/report")
def report():
    """The evaluation from training, and the comparison of data sources."""
    return {
        "evaluation": json.loads((MODELS_DIR / "evaluation_report.json").read_text()),
        "source_comparison": json.loads((MODELS_DIR / "source_comparison.json").read_text()),
    }


@app.get("/predict/{location}")
def predict_from_backfill(location: str):
    """Predict using recent weather fetched from Open-Meteo."""
    loc = find_location(location)
    try:
        records = fetch_history(loc["lat"], loc["lon"])
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Could not fetch recent weather: {type(e).__name__}")
    return run_prediction(location, records)


@app.post("/predict")
def predict_from_readings(request: PredictRequest):
    """Predict using hourly readings supplied by the caller (the backend, from Step 5)."""
    find_location(request.location)
    if not request.readings:
        raise HTTPException(status_code=422, detail="No readings supplied.")
    return run_prediction(request.location, pd.DataFrame([r.model_dump() for r in request.readings]))
