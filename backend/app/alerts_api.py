"""The user's own alerts and notifications, and the live connection to their browser."""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.alerts import EAT, EVENT_LABEL, first_check_time, notification_data, utc_now
from app.auth import active_user, check_location, current_user, decode_token
from app.config import SMTP_HOST
from app.db import Notification, SessionLocal, Subscription, User
from app.realtime import async_client, channel
from app.sms import sms_enabled

router = APIRouter(prefix="/api")

MAX_SUBSCRIPTIONS = 50
MAX_TRIP_DAYS_AHEAD = 30
SOCKET_AUTH_SECONDS = 10


class SubscriptionRequest(BaseModel):
    kind: Literal["always", "daily", "trip"]
    location: str
    email: bool = False
    event: str | None = None  # always
    min_band: Literal["likely", "very_likely"] = "likely"  # always
    time_of_day: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")  # daily: East Africa Time
    trip_at: datetime | None = None  # trip


class ActiveRequest(BaseModel):
    active: bool


class ReadRequest(BaseModel):
    ids: list[int] | None = None  # leave out to mark everything read


def utc_text(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def subscription_data(subscription, now):
    data = {
        "id": subscription.id,
        "kind": subscription.kind,
        "location": subscription.location,
        "active": subscription.active,
        "email": subscription.email,
    }
    if subscription.kind == "always":
        data |= {"event": subscription.event, "min_band": subscription.min_band}
    elif subscription.kind == "daily":
        hours, minutes = divmod(subscription.minutes_eat, 60)
        data |= {"time_of_day": f"{hours:02d}:{minutes:02d}"}
    else:
        data |= {
            "trip_at": utc_text(subscription.trip_at),
            "checked": subscription.trip_ranks is not None,
            "first_check_at": utc_text(first_check_time(subscription.trip_at, now)),
        }
    return data


def parse_minutes(text):
    match = re.fullmatch(r"(\d{2}):(\d{2})", text)
    hours, minutes = int(match[1]), int(match[2])
    if hours > 23 or minutes > 59:
        raise HTTPException(status_code=422, detail="Enter a valid time.")
    return hours * 60 + minutes


def new_subscription(request, user, session, now):
    subscription = Subscription(user_id=user.id, kind=request.kind, location=request.location, email=request.email)
    existing = select(Subscription).where(
        Subscription.user_id == user.id,
        Subscription.kind == request.kind,
        Subscription.location == request.location,
    )

    if request.kind == "always":
        if request.event not in EVENT_LABEL:
            raise HTTPException(status_code=422, detail="Choose a weather event.")
        if session.scalar(existing.where(Subscription.event == request.event)):
            raise HTTPException(status_code=409, detail="You already have this alert.")
        subscription.event = request.event
        subscription.min_band = request.min_band
        subscription.notified_rank = 0

    elif request.kind == "daily":
        if not request.time_of_day:
            raise HTTPException(status_code=422, detail="Choose a time.")
        minutes = parse_minutes(request.time_of_day)
        if session.scalar(existing.where(Subscription.minutes_eat == minutes)):
            raise HTTPException(status_code=409, detail="You already have this daily check.")
        subscription.minutes_eat = minutes
        # Set after today's time has passed: the first one is tomorrow, not straight away
        local_now = now.astimezone(EAT)
        if local_now.hour * 60 + local_now.minute >= minutes:
            subscription.last_sent_date = local_now.date()

    else:
        trip_at = request.trip_at
        if trip_at is None or trip_at.tzinfo is None:
            raise HTTPException(status_code=422, detail="Choose a date and time.")
        if trip_at <= now:
            raise HTTPException(status_code=422, detail="Choose a time in the future.")
        if trip_at > now + timedelta(days=MAX_TRIP_DAYS_AHEAD):
            raise HTTPException(status_code=422, detail=f"Choose a time within {MAX_TRIP_DAYS_AHEAD} days.")
        subscription.trip_at = trip_at
    return subscription


@router.get("/subscriptions")
def list_subscriptions(user: User = Depends(current_user)):
    now = utc_now()
    with SessionLocal() as session:
        rows = session.scalars(
            select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
        ).all()
        return [subscription_data(row, now) for row in rows]


@router.post("/subscriptions", status_code=201)
def create_subscription(request: SubscriptionRequest, user: User = Depends(current_user)):
    check_location(request.location)
    if request.email and not user.email:
        raise HTTPException(status_code=422, detail="Add an email address on the Account page to get alerts by email.")
    now = utc_now()
    with SessionLocal.begin() as session:
        count = session.scalar(select(func.count()).select_from(Subscription).where(Subscription.user_id == user.id))
        if count >= MAX_SUBSCRIPTIONS:
            raise HTTPException(status_code=409, detail=f"You can have up to {MAX_SUBSCRIPTIONS} alerts.")
        subscription = new_subscription(request, user, session, now)
        session.add(subscription)
        session.flush()
        return subscription_data(subscription, now)


def own_subscription(session, subscription_id, user):
    # Another user's alert gets the same answer as one that doesn't exist
    subscription = session.get(Subscription, subscription_id)
    if subscription is None or subscription.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return subscription


@router.patch("/subscriptions/{subscription_id}")
def set_subscription_active(subscription_id: int, request: ActiveRequest, user: User = Depends(current_user)):
    now = utc_now()
    with SessionLocal.begin() as session:
        subscription = own_subscription(session, subscription_id, user)
        if subscription.kind == "trip" and subscription.trip_at <= now and request.active:
            raise HTTPException(status_code=422, detail="This trip has already passed.")
        subscription.active = request.active
        if request.active and subscription.kind == "always":
            subscription.notified_rank = 0  # a likely event should alert when it's turned back on
        return subscription_data(subscription, now)


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def delete_subscription(subscription_id: int, user: User = Depends(current_user)):
    with SessionLocal.begin() as session:
        session.delete(own_subscription(session, subscription_id, user))


@router.get("/notifications")
def list_notifications(user: User = Depends(current_user)):
    with SessionLocal() as session:
        rows = session.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(100)
        ).all()
        return [notification_data(row) for row in rows]


@router.post("/notifications/read", status_code=204)
def mark_read(request: ReadRequest, user: User = Depends(current_user)):
    statement = (
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utc_now())
    )
    if request.ids is not None:
        statement = statement.where(Notification.id.in_(request.ids))
    with SessionLocal.begin() as session:
        session.execute(statement)


@router.get("/alert-options")
def alert_options():
    return {"email_enabled": bool(SMTP_HOST), "sms_enabled": sms_enabled()}


@router.websocket("/ws")
async def notification_socket(socket: WebSocket):
    """Sends new notifications as they happen. The login token is sent as the first message,
    because a token in the address would be written to server logs."""
    await socket.accept()
    try:
        token = await asyncio.wait_for(socket.receive_text(), SOCKET_AUTH_SECONDS)
        user_id, expires = decode_token(token)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        await close_quietly(socket)
        return
    if await run_in_threadpool(active_user, user_id) is None:
        await close_quietly(socket)
        return

    pubsub = async_client.pubsub()
    tasks = set()
    try:
        await pubsub.subscribe(channel(user_id))

        async def forward():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await socket.send_text(message["data"].decode())

        async def wait_for_close():
            while True:
                await socket.receive_text()

        tasks = {asyncio.create_task(forward()), asyncio.create_task(wait_for_close())}
        # Ends when the browser leaves, Redis fails, or the login expires
        seconds_left = max(0, expires - datetime.now(timezone.utc).timestamp())
        await asyncio.wait(tasks, timeout=seconds_left, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await pubsub.aclose()
        await close_quietly(socket)


async def close_quietly(socket):
    try:
        await socket.close(code=4401)
    except (RuntimeError, WebSocketDisconnect):
        pass  # already closed
