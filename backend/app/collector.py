"""Fetches predictions for every location from the ML service and stores them."""
import logging
import threading
import time
from datetime import datetime
from urllib.parse import quote

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.config import ML_SERVICE_URL, POLL_INTERVAL_MINUTES
from app.db import Prediction, SessionLocal

log = logging.getLogger("uvicorn.error")

PAUSE_BETWEEN_LOCATIONS_SECONDS = 0.5  # keeps the calls to Open-Meteo gentle
RETRY_AFTER_FAILURE_SECONDS = 60


def save_run(run):
    """Store one location's prediction run. Re-running the same hour updates its rows."""
    issued_at = datetime.fromisoformat(run["issued_at"])
    rows = [
        {
            "location": run["location"],
            "event": p["event"],
            "category": p["category"],
            "probability": p["probability"],
            "band": p["band"],
            "issued_at": issued_at,
            "valid_from": datetime.fromisoformat(p["valid_from"]),
            "valid_to": datetime.fromisoformat(p["valid_to"]),
            "model_version": run["model_version"],
        }
        for p in run["predictions"]
    ]
    statement = insert(Prediction).values(rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_prediction_location_event_issued",
        set_={
            column: statement.excluded[column]
            for column in ("probability", "band", "valid_from", "valid_to", "model_version")
        },
    )
    with SessionLocal.begin() as session:
        session.execute(statement)


def collect_once():
    """Collect every location. One location failing doesn't stop the others. Returns the number saved."""
    saved = 0
    with httpx.Client(base_url=ML_SERVICE_URL, timeout=60) as client:
        locations = client.get("/locations").raise_for_status().json()
        for location in locations:
            name = location["name"]
            try:
                save_run(client.get(f"/predict/{quote(name)}").raise_for_status().json())
                saved += 1
            except httpx.HTTPError as e:
                log.warning("Could not get predictions for %s: %s", name, e)
            time.sleep(PAUSE_BETWEEN_LOCATIONS_SECONDS)
    log.info("Collected predictions for %d of %d locations", saved, len(locations))
    return saved


def run_forever(stop):
    """Collect on a schedule until `stop` is set. Retries sooner if a whole run saved nothing."""
    while not stop.is_set():
        try:
            saved = collect_once()
        except Exception:
            # Keep the schedule alive through any failure, such as the database restarting
            log.exception("Collection run failed")
            saved = 0
        stop.wait(POLL_INTERVAL_MINUTES * 60 if saved else RETRY_AFTER_FAILURE_SECONDS)


def start_collector():
    stop = threading.Event()
    thread = threading.Thread(target=run_forever, args=(stop,), daemon=True, name="collector")
    thread.start()
    return stop
