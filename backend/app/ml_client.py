"""Reads the data from the ML service that doesn't change while it runs."""
from functools import lru_cache

import httpx
from fastapi import HTTPException

from app.config import ML_SERVICE_URL


@lru_cache(maxsize=None)  # failures raise an error, so they aren't cached
def _fetch(path):
    return httpx.get(f"{ML_SERVICE_URL}{path}", timeout=30).raise_for_status().json()


def static_ml_data(path):
    try:
        return _fetch(path)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="The ML service is not available.")


def location_names():
    return {location["name"] for location in static_ml_data("/locations")}
