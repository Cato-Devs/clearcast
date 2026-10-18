"""Step 1 - Historical data acquisition.

Downloads hourly ERA5 reanalysis weather (Hersbach et al., 2020) for every location in
locations.py through the Open-Meteo archive API (free, no API key).

Run from the ml-service folder:
    python -m training.fetch_historical              # 2010-2025
    python -m training.fetch_historical --start 2020 --end 2021

Downloads are cached per location/year in data/raw/chunks/, so if the script stops
(network drop, rate limit) just run it again and it resumes where it left off.
"""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from training.locations import LOCATIONS

try:
    # Use the operating system's certificate store. Fixes CERTIFICATE_VERIFY_FAILED on
    # Windows machines where antivirus/proxy software inspects HTTPS traffic.
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo variable -> ClearCast column name.
# Names and units match OpenWeather/Tomorrow.io so the model sees the same kind of
# values in training and in production.
VARIABLES = {
    "temperature_2m": "temperature",  # degC
    "relative_humidity_2m": "humidity",  # %
    "pressure_msl": "pressure",  # hPa at sea level (= OpenWeather main.pressure)
    "wind_speed_10m": "wind_speed",  # m/s
    "wind_direction_10m": "wind_deg",  # degrees
    "wind_gusts_10m": "wind_gust",  # m/s
    "precipitation": "rainfall",  # mm in the preceding hour
    "cloud_cover": "cloud_cover",  # %
    "weather_code": "weather_code",  # WMO code (ERA5 never reports thunderstorm codes 95-99)
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
CHUNK_DIR = DATA_DIR / "chunks"
OUTPUT = DATA_DIR / "historical_hourly.csv"


def fetch_year(loc, year, retries=5):
    # ERA5 is published with a ~5 day delay, so never ask for the last week.
    end = min(date(year, 12, 31), date.today() - timedelta(days=7))
    params = {
        "latitude": loc["lat"],
        "longitude": loc["lon"],
        "start_date": f"{year}-01-01",
        "end_date": end.isoformat(),
        "hourly": ",".join(VARIABLES),
        "models": "era5",
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(ARCHIVE_URL, params=params, timeout=120)
        except requests.RequestException as e:
            print(f"  network error ({e}), retrying")
            time.sleep(10 * attempt)
            continue
        if r.status_code == 429:
            print(f"  rate limited, waiting {60 * attempt}s")
            time.sleep(60 * attempt)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"{loc['name']} {year}: HTTP {r.status_code} {r.text[:200]}")
        df = pd.DataFrame(r.json()["hourly"]).rename(columns={"time": "timestamp", **VARIABLES})
        df.insert(0, "location", loc["name"])
        return df
    raise RuntimeError(f"Gave up on {loc['name']} {year} after {retries} attempts")


def summarise(df):
    print(f"\nSaved {len(df):,} rows to {OUTPUT}")
    print(f"Period: {df.timestamp.min()} -> {df.timestamp.max()}\n")
    wet = df[df.rainfall > 0]
    summary = df.groupby("location").agg(
        rows=("timestamp", "size"),
        missing_pct=("temperature", lambda s: round(100 * s.isna().mean(), 2)),
        temp_mean=("temperature", "mean"),
        temp_max=("temperature", "max"),
        rain_max_1h=("rainfall", "max"),
        gust_max=("wind_gust", "max"),
    )
    summary["rain_p99_wet_hours"] = wet.groupby("location").rainfall.quantile(0.99)
    print(summary.round(1).to_string())


def main():
    ap = argparse.ArgumentParser(description="Download ERA5 hourly history for ClearCast locations")
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--end", type=int, default=2025)
    args = ap.parse_args()

    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for loc in LOCATIONS:
        for year in range(args.start, args.end + 1):
            path = CHUNK_DIR / f"{loc['name']}_{year}.csv"
            paths.append(path)
            if path.exists():
                continue
            print(f"Fetching {loc['name']} {year}")
            fetch_year(loc, year).to_csv(path, index=False)
            time.sleep(2)  # stay well inside Open-Meteo's free-tier limits

    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    df = df.drop_duplicates(["location", "timestamp"]).sort_values(["location", "timestamp"])
    df.to_csv(OUTPUT, index=False)
    summarise(df)


if __name__ == "__main__":
    main()
