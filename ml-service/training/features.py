"""Cleaning and feature engineering, shared by training (Step 2) and the live ML service (Step 4).

Using this one module in both places guarantees the model sees features computed in exactly
the same way in training and in production.

Every feature uses only the CURRENT and PAST hours, never the future, so the model can be
used for real early warning. Timestamps are UTC.
"""
import numpy as np
import pandas as pd

RAW_COLUMNS = ["temperature", "humidity", "pressure", "wind_speed", "wind_deg", "wind_gust", "rainfall", "cloud_cover"]

# Physically plausible ranges for Kenya. Values outside them are sensor/API errors.
VALID_RANGES = {
    "temperature": (-5, 50),  # degC
    "humidity": (0, 100),  # %
    "pressure": (950, 1050),  # hPa, sea level
    "wind_speed": (0, 60),  # m/s
    "wind_deg": (0, 360),  # degrees
    "wind_gust": (0, 80),  # m/s
    "rainfall": (0, 200),  # mm/h
    "cloud_cover": (0, 100),  # %
}

HISTORY_HOURS = 48  # the longest look-back window below; live predictions need this much history


def clean(records):
    """Clean one location's records and return a regular hourly series indexed by timestamp.

    1. sort and drop duplicate timestamps
    2. insert any missing hours as empty rows
    3. blank out physically impossible values
    4. forward-fill short gaps (up to 3 h), then mean-impute anything left
    """
    g = records.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    g = g[RAW_COLUMNS].asfreq("h")
    for col, (lo, hi) in VALID_RANGES.items():
        g[col] = g[col].where(g[col].between(lo, hi))
    g = g.ffill(limit=3)
    return g.fillna(g.mean())


def build_features(g):
    """Turn a cleaned hourly series into the model's feature table (one row per hour)."""
    f = pd.DataFrame(index=g.index)

    # Current readings
    for col in ["temperature", "humidity", "pressure", "wind_speed", "wind_gust", "rainfall", "cloud_cover"]:
        f[col] = g[col]

    # Rolling windows over the past 3, 6 and 24 hours
    for h in (3, 6, 24):
        f[f"temp_mean_{h}h"] = g.temperature.rolling(h).mean()
        f[f"rain_sum_{h}h"] = g.rainfall.rolling(h).sum()
    f["rain_sum_48h"] = g.rainfall.rolling(HISTORY_HOURS).sum()  # how saturated the ground is
    f["humidity_mean_6h"] = g.humidity.rolling(6).mean()
    f["gust_max_6h"] = g.wind_gust.rolling(6).max()

    # Rates of change (falling pressure and rising humidity come before rain and storms)
    for h in (3, 6, 24):
        f[f"pressure_change_{h}h"] = g.pressure.diff(h)
    f["temp_change_3h"] = g.temperature.diff(3)
    f["humidity_change_3h"] = g.humidity.diff(3)

    # Dew point depression (Magnus formula): a small gap between temperature and dew point
    # means the air is close to saturation.
    rh = g.humidity.clip(lower=1) / 100
    gamma = np.log(rh) + 17.62 * g.temperature / (243.12 + g.temperature)
    f["dew_point_depression"] = g.temperature - 243.12 * gamma / (17.62 - gamma)

    # Cyclic encoding, so 359 deg is close to 1 deg and December is close to January
    wind = np.deg2rad(g.wind_deg)
    f["wind_dir_sin"], f["wind_dir_cos"] = np.sin(wind), np.cos(wind)
    hour = 2 * np.pi * g.index.hour / 24
    f["hour_sin"], f["hour_cos"] = np.sin(hour), np.cos(hour)
    day = 2 * np.pi * g.index.dayofyear / 365.25  # captures the long (MAM) and short (OND) rains
    f["season_sin"], f["season_cos"] = np.sin(day), np.cos(day)
    return f
