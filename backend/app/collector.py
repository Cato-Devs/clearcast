"""Fetches predictions for every location from the ML service and stores them."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.alerts import process_always_alerts
from app.config import ML_SERVICE_URL, POLL_INTERVAL_MINUTES
from app.db import ApiCall, Collection, CurrentWeather, Prediction, PredictionSnapshot, SessionLocal
from app.live_weather import current_reading

log = logging.getLogger("uvicorn.error")

PAUSE_BETWEEN_LOCATIONS_SECONDS = 0.5  # keeps the calls to the weather APIs gentle
RETRY_AFTER_FAILURE_SECONDS = 60
KEEP_COLLECTIONS_DAYS = 14


def save_run(run, collection_id, live):
    """Store one location's prediction run and its current weather. Re-running the same hour updates its rows."""
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
    snapshots = [
        PredictionSnapshot(
            collection_id=collection_id,
            location=row["location"],
            event=row["event"],
            issued_at=row["issued_at"],
            band=row["band"],
            probability=row["probability"],
        )
        for row in rows
    ]
    _, sources, observed_at, description = live
    current = run["current"]
    weather = CurrentWeather(
        collection_id=collection_id,
        location=run["location"],
        issued_at=issued_at,
        observed_at=observed_at,
        values=current["values"],
        sources={field: sources[field] if field in current["live_fields"] else "open_meteo" for field in sources},
        description=description,
    )
    with SessionLocal.begin() as session:
        session.execute(statement)
        session.add_all(snapshots)
        session.add(weather)


def collect_once():
    """Collect every location. One location failing doesn't stop the others. Returns the number saved."""
    with SessionLocal.begin() as session:
        collection = Collection()
        session.add(collection)
        session.flush()
        collection_id = collection.id

    failed = []
    saved = 0
    total = 0
    try:
        with httpx.Client(base_url=ML_SERVICE_URL, timeout=60) as client, httpx.Client(timeout=20) as api_client:
            locations = client.get("/locations").raise_for_status().json()
            total = len(locations)
            for location in locations:
                name = location["name"]
                try:
                    live = current_reading(api_client, location)
                    run = client.post(f"/predict/{quote(name)}/live", json=live[0]).raise_for_status().json()
                    save_run(run, collection_id, live)
                    saved += 1
                except httpx.HTTPError as e:
                    failed.append(name)
                    log.warning("Could not get predictions for %s: %s", name, e)
                time.sleep(PAUSE_BETWEEN_LOCATIONS_SECONDS)
    finally:
        with SessionLocal.begin() as session:
            collection = session.get(Collection, collection_id)
            collection.finished_at = datetime.now(timezone.utc)
            collection.total = total
            collection.saved = saved
            collection.failed = failed
    log.info("Collected predictions for %d of %d locations", saved, total)
    return saved


def remove_old_collections():
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_COLLECTIONS_DAYS)
    with SessionLocal.begin() as session:
        session.execute(delete(Collection).where(Collection.started_at < cutoff))
        session.execute(delete(ApiCall).where(ApiCall.called_at < cutoff))


def run_forever(stop):
    """Collect on a schedule until `stop` is set. Retries sooner if a whole run saved nothing."""
    while not stop.is_set():
        try:
            saved = collect_once()
            if saved:
                process_always_alerts()
            remove_old_collections()
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
