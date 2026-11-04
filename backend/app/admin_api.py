"""Admin-only views: system health, model results, users and the alert log."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.alerts import MAX_DATA_AGE, utc_now
from app.auth import current_admin
from app.db import Collection, Notification, Prediction, SessionLocal, Subscription, User
from app.ml_client import static_ml_data

# Every route in this file needs an admin. Setting it here means none can be left unprotected.
router = APIRouter(prefix="/api/admin", dependencies=[Depends(current_admin)])

# How often a band changed between collections of the same data hour
BAND_CHANGES_SQL = text(
    """
    SELECT count(*) FILTER (WHERE previous IS NOT NULL) AS comparisons,
           count(*) FILTER (WHERE previous IS NOT NULL AND previous <> band) AS changes
    FROM (
        SELECT band,
               lag(band) OVER (PARTITION BY location, event, issued_at ORDER BY collection_id) AS previous
        FROM prediction_snapshots
    ) AS compared
    """
)


def utc_text(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


@router.get("/overview")
def overview():
    now = utc_now()
    with SessionLocal() as session:
        latest = session.scalar(
            select(Collection)
            .where(Collection.finished_at.is_not(None))
            .order_by(Collection.id.desc())
            .limit(1)
        )
        newest_by_location = session.execute(
            select(Prediction.location, func.max(Prediction.issued_at)).group_by(Prediction.location)
        ).all()
        locations = static_ml_data("/locations")
        newest = dict(newest_by_location)
        count = lambda query: session.scalar(select(func.count()).select_from(query))
        changes = session.execute(BAND_CHANGES_SQL).one()
        return {
            "latest_collection": latest
            and {
                "started_at": utc_text(latest.started_at),
                "finished_at": utc_text(latest.finished_at),
                "total": latest.total,
                "saved": latest.saved,
                "failed": latest.failed,
            },
            "stale_locations": sorted(
                location["name"]
                for location in locations
                if location["name"] not in newest or now - newest[location["name"]] > MAX_DATA_AGE
            ),
            "location_count": len(locations),
            "users": count(User),
            "active_alerts": count(select(Subscription).where(Subscription.active).subquery()),
            "notifications_24h": count(
                select(Notification).where(Notification.created_at >= now - timedelta(hours=24)).subquery()
            ),
            "emails_failed": count(select(Notification).where(Notification.email_status == "failed").subquery()),
            "band_changes": {"comparisons": changes.comparisons, "changes": changes.changes},
        }


@router.get("/model")
def model():
    return static_ml_data("/report")


@router.get("/users")
def users():
    with SessionLocal() as session:
        alerts = (
            select(Subscription.user_id, func.count().label("alerts"))
            .where(Subscription.active)
            .group_by(Subscription.user_id)
            .subquery()
        )
        rows = session.execute(
            select(User, func.coalesce(alerts.c.alerts, 0))
            .outerjoin(alerts, User.id == alerts.c.user_id)
            .order_by(User.created_at.desc())
        ).all()
        return [
            {
                "id": user.id,
                "email": user.email,
                "home_location": user.home_location,
                "is_admin": user.is_admin,
                "is_active": user.is_active,
                "created_at": utc_text(user.created_at),
                "active_alerts": active_alerts,
            }
            for user, active_alerts in rows
        ]


class UserActiveRequest(BaseModel):
    is_active: bool


@router.patch("/users/{user_id}")
def set_user_active(user_id: int, request: UserActiveRequest):
    with SessionLocal.begin() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.is_admin:
            raise HTTPException(status_code=409, detail="The admin account can't be disabled here.")
        user.is_active = request.is_active
        return {"id": user.id, "is_active": user.is_active}


@router.get("/alerts")
def alert_log():
    with SessionLocal() as session:
        rows = session.execute(
            select(Notification, User.email)
            .join(User, Notification.user_id == User.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(100)
        ).all()
        return [
            {
                "id": notification.id,
                "email": email,
                "kind": notification.kind,
                "location": notification.location,
                "title": notification.title,
                "created_at": utc_text(notification.created_at),
                "email_status": notification.email_status,
            }
            for notification, email in rows
        ]
