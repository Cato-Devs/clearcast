"""Step 2 - Preprocessing and labelling.

Turns data/raw/historical_hourly.csv into a model-ready dataset:
  1. clean each location's hourly series                    (features.clean)
  2. engineer features from the current and past hours      (features.build_features)
  3. give every hour a yes/no target per weather event, based on the FOLLOWING hours
  4. split by date into train / validation / test / final

Run from the ml-service folder:
    python -m training.prepare_dataset
"""
from pathlib import Path

import numpy as np
import pandas as pd

from training.features import build_features, clean

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW = DATA_DIR / "raw" / "historical_hourly.csv"
OUTPUT = DATA_DIR / "processed" / "dataset.csv"

# The events ClearCast predicts, grouped the way users see them. Each event gets its own
# yes/no model whose probability is shown as very unlikely / unlikely / likely / very likely.
EVENT_CATEGORIES = {
    "rain": ["rain", "heavy_rain", "flood_risk"],
    "temperature": ["hot", "cold"],
    "sky": ["sunny"],
    "wind": ["strong_wind", "storm"],
}
EVENTS = [e for events in EVENT_CATEGORIES.values() for e in events]

# Event thresholds, chosen from the 2010-2025 ERA5 data for the 7 towns.
# ERA5 smooths out extremes, so rain thresholds sit below station-based KMD warning levels.
RAIN_6H_MM = 1  # rain: any meaningful rain in the next 6 h
HEAVY_RAIN_6H_MM = 10  # heavy_rain: rain in the next 6 h
FLOOD_TOTAL_MM = 50  # flood_risk: rain in the past 48 h + next 24 h (rain on saturated ground)
FLOOD_NEXT_24H_MM = 10  # ...with at least this much still to come
HOT_C = 35  # hot: highest temperature in the next 6 h
COLD_C = 12  # cold: lowest temperature in the next 6 h
SUNNY_CLOUD_PCT = 30  # sunny: average cloud cover in the next 6 h
STRONG_GUST_MS = 12  # strong_wind: strongest gust in the next 6 h (~43 km/h)
STORM_RAIN_6H_MM = 3  # storm: strong gusts together with at least this much rain

# Chronological holdout. The test period contains the 2023 El Nino floods and the April-May
# 2024 floods. Test results influenced the choice of the "likely" cut-off, so 2026 is kept
# as the final holdout: nothing may be changed after seeing its results.
TRAIN_END = pd.Timestamp("2021-12-31 23:00")
VAL_END = pd.Timestamp("2022-12-31 23:00")
TEST_END = pd.Timestamp("2025-12-31 23:00")
SPLITS = ["train", "val", "test", "final"]


def next_hours(s, hours, how):
    """sum/max/min/mean of the `hours` values AFTER each timestamp (t+1 .. t+hours)."""
    # Rounded because rolling sums drift by ~1e-14, which flips labels sitting exactly on a threshold
    return getattr(s[::-1].rolling(hours), how)()[::-1].shift(-1).round(6)


def make_targets(g):
    rain6 = next_hours(g.rainfall, 6, "sum")
    rain24 = next_hours(g.rainfall, 24, "sum")
    gust6 = next_hours(g.wind_gust, 6, "max")
    past48 = g.rainfall.rolling(48).sum().round(6)

    targets = pd.DataFrame(
        {
            "rain": rain6 >= RAIN_6H_MM,
            "heavy_rain": rain6 >= HEAVY_RAIN_6H_MM,
            "flood_risk": (past48 + rain24 >= FLOOD_TOTAL_MM) & (rain24 >= FLOOD_NEXT_24H_MM),
            "hot": next_hours(g.temperature, 6, "max") >= HOT_C,
            "cold": next_hours(g.temperature, 6, "min") <= COLD_C,
            "sunny": next_hours(g.cloud_cover, 6, "mean") <= SUNNY_CLOUD_PCT,
            "strong_wind": gust6 >= STRONG_GUST_MS,
            "storm": (gust6 >= STRONG_GUST_MS) & (rain6 >= STORM_RAIN_6H_MM),
        }
    ).astype(float)
    targets.loc[rain24.isna()] = np.nan  # the final 24 h have no complete future to label from
    return targets


def report(df):
    print(f"Saved {len(df):,} rows x {df.shape[1]} columns to {OUTPUT}\n")
    print("Rows per split:", df.split.value_counts().reindex(SPLITS).to_dict())
    print("\nHow often each event happens, % of hours per split:")
    print((100 * df.groupby("split")[EVENTS].mean()).reindex(SPLITS).T.round(2).to_string())
    print("\nHow often each event happens, % of hours per location:")
    print((100 * df.groupby("location")[EVENTS].mean()).T.round(2).to_string())


def main():
    raw = pd.read_csv(RAW, parse_dates=["timestamp"])
    parts = []
    for loc, records in raw.groupby("location"):
        g = clean(records)
        part = build_features(g).join(make_targets(g))
        part.insert(0, "location", loc)
        parts.append(part)

    # dropna removes each location's first 48 h (rolling windows not yet full) and last 24 h (no targets)
    df = pd.concat(parts).dropna().rename_axis("timestamp").reset_index()
    df[EVENTS] = df[EVENTS].astype(int)
    df["split"] = "train"
    df.loc[df.timestamp > TRAIN_END, "split"] = "val"
    df.loc[df.timestamp > VAL_END, "split"] = "test"
    df.loc[df.timestamp > TEST_END, "split"] = "final"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False, float_format="%.3f")
    report(df)


if __name__ == "__main__":
    main()
