"""ClearCast backend API. Interactive API docs are at /docs when it is running."""
from contextlib import asynccontextmanager
from datetime import timezone

from fastapi import FastAPI
from sqlalchemy import select, text

from app.admin_api import router as admin_router
from app.alerts import start_alert_loop
from app.alerts_api import router as alerts_router
from app.auth import router as auth_router
from app.auth import seed_admin
from app.collector import start_collector
from app.db import Prediction, SessionLocal, create_tables
from app.ml_client import static_ml_data


@asynccontextmanager
async def lifespan(app):
    create_tables()
    seed_admin()
    stop_collector = start_collector()
    stop_alerts = start_alert_loop()
    yield
    stop_collector.set()
    stop_alerts.set()


app = FastAPI(title="ClearCast API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(alerts_router)
app.include_router(admin_router)


def utc_text(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


@app.get("/api/about")
def about():
    """The public summary of how well the models perform, for the About page."""
    report = static_ml_data("/report")
    keep = ("recall", "precision", "f1", "positives")
    return {
        "events": {
            event: {
                "test": {key: result["test"][key] for key in keep},
                "final": {key: result["final"][key] for key in keep},
            }
            for event, result in report["evaluation"].items()
            if event != "storm"  # evaluated, but not offered as an alert
        },
        "source_comparison": report["source_comparison"],
    }


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
