"""Turns hourly weather into predictions, in the format set out in docs/prediction-format.md."""
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
import sklearn

from training.features import HISTORY_HOURS, RAW_COLUMNS, build_features, clean
from training.prepare_dataset import EVENT_CATEGORIES

BUNDLE_PATH = Path(__file__).resolve().parent.parent / "models" / "clearcast_models.joblib"

CATEGORY_OF_EVENT = {event: category for category, events in EVENT_CATEGORIES.items() for event in events}
WINDOW_HOURS = {"flood_risk": 24}  # every other event looks 6 hours ahead
DEFAULT_WINDOW_HOURS = 6

# clean() can fill small gaps, but a window with many gaps would give a made-up prediction
MAX_MISSING_HOURS = 6


class NotEnoughData(ValueError):
    """The readings cannot support a prediction."""


@lru_cache(maxsize=1)
def load_bundle():
    bundle = joblib.load(BUNDLE_PATH)
    if bundle["sklearn_version"] != sklearn.__version__:
        raise RuntimeError(
            f"Models were saved with scikit-learn {bundle['sklearn_version']} "
            f"but this is {sklearn.__version__}. Use the version in requirements.txt."
        )
    return bundle


def band_for(probability, cutoffs):
    if probability >= cutoffs["very_likely"]:
        return "very_likely"
    if probability >= cutoffs["likely"]:
        return "likely"
    if probability >= cutoffs["unlikely"]:
        return "unlikely"
    return "very_unlikely"


def latest_features(records):
    """Build the feature row for the latest hour in `records`. Returns (features, issued_at)."""
    records = records.copy()
    # Times without a zone are treated as UTC. The rest of the code uses plain UTC times.
    records["timestamp"] = pd.to_datetime(records["timestamp"], utc=True).dt.tz_localize(None)
    issued_at = records["timestamp"].max()
    hours = pd.date_range(end=issued_at, periods=HISTORY_HOURS, freq="h", name="timestamp")

    window = records.drop_duplicates("timestamp").set_index("timestamp")[RAW_COLUMNS].reindex(hours)
    worst_column = window.isna().sum().max()
    if worst_column > MAX_MISSING_HOURS:
        raise NotEnoughData(
            f"Up to {MAX_MISSING_HOURS} of the last {HISTORY_HOURS} hours can be missing, "
            f"but one weather field is missing {worst_column}."
        )

    features = build_features(clean(window.reset_index())).iloc[[-1]]
    if features.isna().any(axis=None):
        raise NotEnoughData("The readings contain a weather field with no usable values.")
    return features, issued_at


def predict_run(location, records):
    """Predict all events for one location from its hourly readings."""
    bundle = load_bundle()
    features, issued_at = latest_features(records)
    X = features[bundle["features"]].astype("float32")

    issued = issued_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    predictions = []
    for event, spec in bundle["events"].items():
        probability = float(spec["model"].predict_proba(X)[0, 1])
        window = WINDOW_HOURS.get(event, DEFAULT_WINDOW_HOURS)
        predictions.append(
            {
                "event": event,
                "category": CATEGORY_OF_EVENT[event],
                "probability": round(probability, 4),
                "band": band_for(probability, spec["cutoffs"]),
                "valid_from": issued,
                "valid_to": (issued_at + timedelta(hours=window)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return {
        "location": location,
        "issued_at": issued,
        "model_version": bundle["version"],
        "predictions": predictions,
    }
