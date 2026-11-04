"""Decides when to notify people, for the three kinds of alert.

always: an event reaches the chosen band at a location.
daily:  a briefing at a set time, sent even if all is clear.
trip:   a check on one place and time, sent once the predictions reach that time, and again if
        the outlook gets worse.

Predictions can change between collections within the same hour. So "always" alerts and trip
updates only act on a band that has held for CONFIRM_COLLECTIONS collections in a row.
"""
import logging
import smtplib
import threading
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from app.db import Notification, Prediction, PredictionSnapshot, SessionLocal, Subscription
from app.realtime import publish

log = logging.getLogger("uvicorn.error")

EAT = timezone(timedelta(hours=3))
BAND_RANK = {"very_unlikely": 0, "unlikely": 1, "likely": 2, "very_likely": 3}
BAND_LABEL = {"very_unlikely": "very unlikely", "unlikely": "unlikely", "likely": "likely", "very_likely": "very likely"}
EVENT_LABEL = {
    "rain": "Rain",
    "heavy_rain": "Heavy rain",
    "flood_risk": "Flood risk",
    "hot": "Hot weather",
    "cold": "Cold weather",
    "sunny": "Clear skies",
    "strong_wind": "Strong wind",
}
ADVERSE_EVENTS = ["heavy_rain", "flood_risk", "strong_wind", "hot", "cold"]
LIKELY = BAND_RANK["likely"]

MAX_DATA_AGE = timedelta(hours=3)  # the same limit the UI uses for "No recent data"
CONFIRM_COLLECTIONS = 2
DAILY_CATCH_UP_MINUTES = 60  # if the system was down at the set time, still send within this long
TICK_SECONDS = 60


def eat_text(moment):
    """For example "Fri 6 Nov, 3:00 pm"."""
    local = moment.astimezone(EAT)
    hour = local.hour % 12 or 12
    return f"{local:%a} {local.day} {local:%b}, {hour}:{local:%M} {'am' if local.hour < 12 else 'pm'}"


def utc_now():
    return datetime.now(timezone.utc)


def current_predictions(session, location, now):
    """The newest prediction per event, if every adverse event has one recent enough to trust."""
    rows = session.scalars(
        select(Prediction)
        .where(Prediction.location == location)
        .distinct(Prediction.event)
        .order_by(Prediction.event, Prediction.issued_at.desc())
    ).all()
    predictions = {row.event: row for row in rows if now - row.issued_at <= MAX_DATA_AGE}
    return predictions if all(event in predictions for event in ADVERSE_EVENTS) else None


def recent_ranks(session, location, event, now):
    """The band ranks from the latest collections, newest first."""
    rows = session.scalars(
        select(PredictionSnapshot)
        .where(
            PredictionSnapshot.location == location,
            PredictionSnapshot.event == event,
            PredictionSnapshot.issued_at >= now - MAX_DATA_AGE,
        )
        .order_by(PredictionSnapshot.collection_id.desc())
        .limit(CONFIRM_COLLECTIONS)
    ).all()
    return [BAND_RANK[row.band] for row in rows]


def add_notification(session, subscription, title, body):
    notification = Notification(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        kind=subscription.kind,
        location=subscription.location,
        title=title,
        body=body,
        created_at=utc_now(),
        email_status="pending" if subscription.email else None,
    )
    session.add(notification)
    return notification


def notification_data(notification):
    return {
        "id": notification.id,
        "kind": notification.kind,
        "location": notification.location,
        "title": notification.title,
        "body": notification.body,
        "created_at": notification.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "read": notification.read_at is not None,
    }


def deliver(session, created):
    """Save the new notifications first, so a delivery failure can't lose them, then send them."""
    session.commit()
    for notification in created:
        publish(notification.user_id, notification_data(notification))


# ---------- Always-on alerts ----------


def process_always_alerts(now=None):
    """Runs after each collection."""
    now = now or utc_now()
    with SessionLocal() as session:
        subscriptions = session.scalars(
            select(Subscription).where(Subscription.kind == "always", Subscription.active)
        ).all()
        created = []
        for subscription in subscriptions:
            ranks = recent_ranks(session, subscription.location, subscription.event, now)
            if len(ranks) < CONFIRM_COLLECTIONS:
                continue
            confirmed, peak = min(ranks), max(ranks)
            threshold = BAND_RANK[subscription.min_band]
            if confirmed >= threshold and confirmed > subscription.notified_rank:
                created.append(always_notification(session, subscription, confirmed, now))
                subscription.notified_rank = confirmed
            elif peak < subscription.notified_rank:
                # It has dropped, so a later rise is news again
                subscription.notified_rank = peak if peak >= threshold else 0
        deliver(session, created)


def always_notification(session, subscription, rank, now):
    band = next(name for name, value in BAND_RANK.items() if value == rank)
    event = EVENT_LABEL[subscription.event]
    prediction = session.scalar(
        select(Prediction)
        .where(Prediction.location == subscription.location, Prediction.event == subscription.event)
        .order_by(Prediction.issued_at.desc())
        .limit(1)
    )
    return add_notification(
        session,
        subscription,
        f"{event} {BAND_LABEL[band]} in {subscription.location}",
        f"Predicted for {eat_text(prediction.valid_from)} to {eat_text(prediction.valid_to)} EAT.",
    )


# ---------- Briefings, shared by daily and trip alerts ----------


def adverse_ranks(predictions):
    return {event: BAND_RANK[predictions[event].band] for event in ADVERSE_EVENTS}


def headline(predictions):
    """For example "heavy rain likely", or how many conditions if there are several."""
    risky = [event for event, rank in adverse_ranks(predictions).items() if rank >= LIKELY]
    if not risky:
        return "no adverse conditions predicted"
    if len(risky) == 1:
        return f"{EVENT_LABEL[risky[0]].lower()} {BAND_LABEL[predictions[risky[0]].band]}"
    return f"{len(risky)} adverse conditions predicted"


def outlook_text(predictions):
    """A sentence per likely condition, and the period the predictions cover."""
    sentences = []
    for event, rank in adverse_ranks(predictions).items():
        if rank >= LIKELY:
            when = " in the next 24 hours" if event == "flood_risk" else ""
            sentences.append(f"{EVENT_LABEL[event]}: {BAND_LABEL[predictions[event].band]}{when}.")
    six_hours = predictions["heavy_rain"]
    sentences.append(f"Predictions cover {eat_text(six_hours.valid_from)} to {eat_text(six_hours.valid_to)} EAT.")
    return " ".join(sentences)


# ---------- Daily briefings ----------


def daily_is_due(subscription, local_now):
    minutes_now = local_now.hour * 60 + local_now.minute
    late_by = minutes_now - subscription.minutes_eat
    return subscription.last_sent_date != local_now.date() and 0 <= late_by <= DAILY_CATCH_UP_MINUTES


def daily_notification(session, subscription, now):
    predictions = current_predictions(session, subscription.location, now)
    if predictions is None:
        # Never "all clear" without data to back it up
        return add_notification(
            session,
            subscription,
            f"{subscription.location} daily check: no recent data",
            "ClearCast has no recent predictions for this location, so it can't say what to expect.",
        )
    return add_notification(
        session,
        subscription,
        f"{subscription.location} daily check: {headline(predictions)}",
        outlook_text(predictions),
    )


# ---------- Trip checks ----------


def first_check_time(trip_at, now):
    """When a trip check first has predictions reaching the trip: the first whole hour within
    6 hours of it, because predictions are issued on the hour and cover the next 6 hours."""
    earliest = trip_at - timedelta(hours=6)
    if earliest <= now:
        return now
    whole_hour = earliest.replace(minute=0, second=0, microsecond=0)
    return whole_hour if whole_hour == earliest else whole_hour + timedelta(hours=1)


def trip_notification(session, subscription, predictions, prefix):
    place = f"{subscription.location}, {eat_text(subscription.trip_at)}"
    return add_notification(
        session,
        subscription,
        f"{prefix}{place}: {headline(predictions)}",
        outlook_text(predictions),
    )


def process_trip(session, subscription, now):
    """Returns a new notification, if there is one to send."""
    if now >= subscription.trip_at:
        subscription.active = False
        if subscription.trip_ranks is None:
            # It's over and no check ever ran. Say so, rather than leave them assuming all is well.
            return add_notification(
                session,
                subscription,
                f"{subscription.location}, {eat_text(subscription.trip_at)}: couldn't be checked",
                "ClearCast had no recent predictions before this time, so this check didn't run.",
            )
        return None

    predictions = current_predictions(session, subscription.location, now)
    if predictions is None or predictions["heavy_rain"].valid_to < subscription.trip_at:
        return None

    if subscription.trip_ranks is None:
        subscription.trip_ranks = adverse_ranks(predictions)
        return trip_notification(session, subscription, predictions, "")

    worse = False
    ranks = dict(subscription.trip_ranks)
    for event in ADVERSE_EVENTS:
        recent = recent_ranks(session, subscription.location, event, now)
        if len(recent) == CONFIRM_COLLECTIONS and min(recent) >= LIKELY and min(recent) > ranks[event]:
            ranks[event] = min(recent)
            worse = True
    if worse:
        subscription.trip_ranks = ranks
        return trip_notification(session, subscription, predictions, "Update: worse outlook for ")
    return None


def process_scheduled_alerts(now=None):
    """Runs every minute: daily briefings and trip checks."""
    now = now or utc_now()
    local_now = now.astimezone(EAT)
    with SessionLocal() as session:
        subscriptions = session.scalars(
            select(Subscription).where(Subscription.kind.in_(["daily", "trip"]), Subscription.active)
        ).all()
        created = []
        for subscription in subscriptions:
            if subscription.kind == "daily":
                if daily_is_due(subscription, local_now):
                    created.append(daily_notification(session, subscription, now))
                    subscription.last_sent_date = local_now.date()
            else:
                notification = process_trip(session, subscription, now)
                if notification:
                    created.append(notification)
        deliver(session, created)


# ---------- Email ----------


def send_email(to, subject, body):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        elif SMTP_USER:
            # Never send the password over a connection that isn't encrypted
            raise smtplib.SMTPException("The mail server doesn't support encryption.")
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        message = EmailMessage()
        message["From"] = SMTP_FROM
        message["To"] = to
        message["Subject"] = f"ClearCast: {subject}"
        message.set_content(f"{body}\n\nManage your alerts on the My Alerts page in ClearCast.")
        smtp.send_message(message)


def send_pending_emails():
    with SessionLocal() as session:
        pending = session.scalars(select(Notification).where(Notification.email_status == "pending")).all()
        for notification in pending:
            if not SMTP_HOST:
                notification.email_status = "not_configured"
                continue
            try:
                send_email(notification.user.email, notification.title, notification.body)
                notification.email_status = "sent"
            except (OSError, smtplib.SMTPException) as e:
                log.warning("Could not send alert email %d: %s", notification.id, e)
                notification.email_status = "failed"
        session.commit()


# ---------- Schedule ----------


def run_forever(stop):
    while not stop.is_set():
        try:
            process_scheduled_alerts()
            send_pending_emails()
        except Exception:
            log.exception("Alert check failed")  # keep the schedule alive
        stop.wait(TICK_SECONDS)


def start_alert_loop():
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(stop,), daemon=True, name="alerts").start()
    return stop
