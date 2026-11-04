"""The 48-hour backfill: recent hourly weather from Open-Meteo (free, no API key).

The models need 48 hours of history, which the free OpenWeather and Tomorrow.io plans don't
provide. The past hours are weather-model estimates, not station measurements.
"""
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Importing this module also applies the certificate fix for Windows machines
from training.fetch_historical import VARIABLES

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Dropped connections and brief server errors are common enough to retry: waits 1, 2, then 4 s
session = requests.Session()
session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])),
)


def fetch_history(lat, lon, now=None):
    """Hourly readings for the past two days up to the current hour, in UTC.

    Two past days plus today always give at least 49 hours, even just after midnight.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(VARIABLES),
        "wind_speed_unit": "ms",
        "past_days": 2,
        "forecast_days": 1,
        "timezone": "GMT",
    }
    response = session.get(FORECAST_URL, params=params, timeout=30)
    response.raise_for_status()

    df = pd.DataFrame(response.json()["hourly"]).rename(columns={"time": "timestamp", **VARIABLES})
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # The response runs to 23:00 today. Later hours are forecasts: they must never be used as
    # readings, because the models were trained on the current and past hours only.
    current_hour = (now or pd.Timestamp.now("UTC").tz_localize(None)).floor("h")
    return df[df["timestamp"] <= current_hour].reset_index(drop=True)
