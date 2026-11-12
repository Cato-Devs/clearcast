"""Admin-only views: system health, live weather sources, model results, users and the alert log."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.alerts import MAX_DATA_AGE, utc_now
from app.alerts_api import subscription_data
from app.auth import current_admin
from app.db import ApiCall, Collection, Notification, Prediction, SessionLocal, Subscription, User
from app.live_weather import SOURCES
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


NEW_USER_DAYS = 7


def source_status(session, now):
    """For each live weather API: whether it's set up, its last success and failure, and recent use."""
    day_ago = now - timedelta(days=1)
    statuses = []
    for source, info in SOURCES.items():
        calls = select(func.count()).select_from(ApiCall).where(ApiCall.source == source, ApiCall.called_at >= day_ago)
        last = lambda ok: session.scalar(
            select(ApiCall).where(ApiCall.source == source, ApiCall.ok == ok).order_by(ApiCall.called_at.desc()).limit(1)
        )
        last_ok, last_failure = last(True), last(False)
        statuses.append(
            {
                "source": source,
                **info,
                "calls_24h": session.scalar(calls),
                "failed_24h": session.scalar(calls.where(ApiCall.ok.is_(False))),
                "calls_last_hour": session.scalar(calls.where(ApiCall.called_at >= now - timedelta(hours=1))),
                "last_ok_at": last_ok and utc_text(last_ok.called_at),
                "last_failure_at": last_failure and utc_text(last_failure.called_at),
                "last_error": last_failure and last_failure.error,
            }
        )
    return statuses


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
            "new_users": count(select(User).where(User.created_at >= now - timedelta(days=NEW_USER_DAYS)).subquery()),
            "new_user_days": NEW_USER_DAYS,
            "sources": source_status(session, now),
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
        sent = (
            select(Notification.user_id, func.count().label("sent"))
            .group_by(Notification.user_id)
            .subquery()
        )
        rows = session.execute(
            select(User, func.coalesce(alerts.c.alerts, 0), func.coalesce(sent.c.sent, 0))
            .outerjoin(alerts, User.id == alerts.c.user_id)
            .outerjoin(sent, User.id == sent.c.user_id)
            .order_by(User.created_at.desc())
        ).all()
        now = utc_now()
        return [
            user_summary(user, now) | {"active_alerts": active_alerts, "notifications": notifications}
            for user, active_alerts, notifications in rows
        ]


def user_summary(user, now):
    return {
        "id": user.id,
        "email": user.email,
        "home_location": user.home_location,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": utc_text(user.created_at),
        "last_login_at": utc_text(user.last_login_at),
        "is_new": now - user.created_at <= timedelta(days=NEW_USER_DAYS),
    }


@router.get("/users/{user_id}")
def user_detail(user_id: int):
    """One user's details, their alert settings, and the notifications ClearCast sent them."""
    now = utc_now()
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        subscriptions = session.scalars(
            select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
        ).all()
        notifications = session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(200)
        ).all()
        return {
            "user": user_summary(user, now),
            "subscriptions": [
                subscription_data(s, now) | {"created_at": utc_text(s.created_at)} for s in subscriptions
            ],
            "notifications": [
                {
                    "id": n.id,
                    "kind": n.kind,
                    "location": n.location,
                    "title": n.title,
                    "body": n.body,
                    "created_at": utc_text(n.created_at),
                    "read_at": utc_text(n.read_at),
                    "email_status": n.email_status,
                }
                for n in notifications
            ],
        }


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
