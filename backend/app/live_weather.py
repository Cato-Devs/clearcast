"""Live weather: fetches the current weather from OpenWeather and Tomorrow.io and combines it.

The models only understand these fields, in these units (see ml-service/training/features.py):
temperature degC, humidity %, pressure hPa at sea level, wind_speed m/s, wind_deg degrees,
wind_gust m/s, rainfall mm in the preceding hour, cloud_cover %.

For each field, OpenWeather is used first, then Tomorrow.io. A field neither sent stays empty,
and the ML service keeps Open-Meteo's estimate for it.

Every call is saved as an ApiCall. That record drives the admin status page, keeps Tomorrow.io
inside its free limits across restarts, and holds Tomorrow.io's latest reading between calls.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select

from app.config import OPENWEATHER_API_KEY, TOMORROW_API_KEY
from app.db import ApiCall, SessionLocal

log = logging.getLogger("uvicorn.error")

FIELDS = ["temperature", "humidity", "pressure", "wind_speed", "wind_deg", "wind_gust", "rainfall", "cloud_cover"]

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
TOMORROW_URL = "https://api.tomorrow.io/v4/weather/realtime"

# Tomorrow.io's free plan allows 25 calls an hour and 500 a day. One call per location every
# 70 minutes is 23 calls each time, about 470 a day. The limits below stop at the plan's limits
# even if something goes wrong, such as the backend restarting many times.
TOMORROW_INTERVAL = timedelta(minutes=70)
TOMORROW_HOURLY_LIMIT = 25
TOMORROW_DAILY_LIMIT = 500
# A Tomorrow.io reading is used to fill gaps until the next one is due, with some leeway
TOMORROW_MAX_AGE = timedelta(minutes=90)

SOURCES = {
    "openweather": {
        "label": "OpenWeather",
        "configured": bool(OPENWEATHER_API_KEY),
        "schedule": "Every collection (every 15 minutes)",
        "limit": "60 calls a minute, 1,000,000 a month",
    },
    "tomorrow": {
        "label": "Tomorrow.io",
        "configured": bool(TOMORROW_API_KEY),
        "schedule": "Every 70 minutes per location",
        "limit": f"{TOMORROW_HOURLY_LIMIT} calls an hour, {TOMORROW_DAILY_LIMIT} a day",
    },
}


def from_openweather(data):
    """Map a response from /data/2.5/weather, requested with units=metric.

    OpenWeather leaves "rain" out when it is dry, so missing rain means 0 mm.
    """
    wind = data["wind"]
    return {
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],  # already at sea level
        "wind_speed": wind["speed"],
        "wind_deg": wind.get("deg"),
        "wind_gust": wind.get("gust"),  # often left out in light wind
        "rainfall": data.get("rain", {}).get("1h", 0.0),
        "cloud_cover": data["clouds"]["all"],
    }


def from_tomorrow(data):
    """Map a response from /v4/weather/realtime, requested with units=metric."""
    values = data["data"]["values"]
    return {
        "temperature": values.get("temperature"),
        "humidity": values.get("humidity"),
        # Not pressureSurfaceLevel: Nairobi's surface pressure is far below its sea-level value
        "pressure": values.get("pressureSeaLevel"),
        "wind_speed": values.get("windSpeed"),
        "wind_deg": values.get("windDirection"),
        "wind_gust": values.get("windGust"),
        "rainfall": values.get("rainIntensity"),  # mm/h right now, used as the hour's rainfall
        "cloud_cover": values.get("cloudCover"),
    }


def utc_now():
    return datetime.now(timezone.utc)


def call_api(client, source, location, url, params, to_reading, observed_at):
    """Call one API, save the call, and return (reading, description, observed time) or None."""
    call = ApiCall(source=source, location=location["name"], ok=False)
    result = None
    try:
        response = client.get(url, params=params)
        call.status_code = response.status_code
        if response.status_code == 200:
            data = response.json()
            call.reading = to_reading(data)
            call.observed_at = observed_at(data)
            call.description = data.get("weather", [{}])[0].get("description") if source == "openweather" else None
            call.ok = True
            result = call.reading, call.description, call.observed_at
        else:
            # Never save the response body or URL: OpenWeather can repeat the key in them
            call.error = f"HTTP {response.status_code}"
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
        call.error = type(e).__name__
    if not call.ok:
        log.warning("%s failed for %s: %s", source, location["name"], call.error)
    with SessionLocal.begin() as session:
        session.add(call)
    return result


def fetch_openweather(client, location):
    if not OPENWEATHER_API_KEY:
        return None
    params = {"lat": location["lat"], "lon": location["lon"], "units": "metric", "appid": OPENWEATHER_API_KEY}
    return call_api(
        client,
        "openweather",
        location,
        OPENWEATHER_URL,
        params,
        from_openweather,
        lambda data: datetime.fromtimestamp(data["dt"], timezone.utc),
    )


def tomorrow_allowed(session, location, now):
    """True if this location's Tomorrow.io call is due and the free limits leave room for it."""
    calls = select(func.count()).select_from(ApiCall).where(ApiCall.source == "tomorrow")
    last_call = session.scalar(
        select(func.max(ApiCall.called_at)).where(ApiCall.source == "tomorrow", ApiCall.location == location["name"])
    )
    if last_call and now - last_call < TOMORROW_INTERVAL:
        return False
    if session.scalar(calls.where(ApiCall.called_at >= now - timedelta(hours=1))) >= TOMORROW_HOURLY_LIMIT:
        return False
    return session.scalar(calls.where(ApiCall.called_at >= now - timedelta(days=1))) < TOMORROW_DAILY_LIMIT


def latest_tomorrow(session, location, now):
    """The newest Tomorrow.io reading for a location, if recent enough to use."""
    call = session.scalar(
        select(ApiCall)
        .where(ApiCall.source == "tomorrow", ApiCall.location == location["name"], ApiCall.ok)
        .order_by(ApiCall.called_at.desc())
        .limit(1)
    )
    if call is None or now - call.called_at > TOMORROW_MAX_AGE:
        return None
    return call.reading, call.description, call.observed_at


def fetch_tomorrow(client, location):
    if not TOMORROW_API_KEY:
        return None
    now = utc_now()
    with SessionLocal() as session:
        allowed = tomorrow_allowed(session, location, now)
    if allowed:
        params = {"location": f"{location['lat']},{location['lon']}", "units": "metric", "apikey": TOMORROW_API_KEY}
        if fresh := call_api(
            client,
            "tomorrow",
            location,
            TOMORROW_URL,
            params,
            from_tomorrow,
            lambda data: datetime.fromisoformat(data["data"]["time"]),
        ):
            return fresh
    with SessionLocal() as session:
        return latest_tomorrow(session, location, now)


def current_reading(client, location):
    """The live reading for one location: (fields for the ML service, source of each field, observed time, description).

    Fields with no live value are None and their source is "open_meteo".
    """
    openweather = fetch_openweather(client, location)
    tomorrow = fetch_tomorrow(client, location)
    fields, sources = {}, {}
    for field in FIELDS:
        for name, result in (("openweather", openweather), ("tomorrow", tomorrow)):
            if result and result[0].get(field) is not None:
                fields[field] = result[0][field]
                sources[field] = name
                break
        else:
            fields[field] = None
            sources[field] = "open_meteo"
    main = openweather or tomorrow
    return fields, sources, main and main[2], openweather and openweather[1]
