"""Step 3 - Model training, validation and testing.

For each weather event this script:
  1. tunes a Random Forest and a Decision Tree with grid search + 5-fold time-series
     cross-validation on the training years (2010-2021)
  2. picks the better model on the validation year (2022) and sets its likelihood band
     cut-offs there
  3. reports performance on the test years (2023-2025), including an operational check
     against documented flood periods, and compares it with simple baseline rules
  4. reports performance on the final holdout (2026). Test results influenced the "likely"
     cut-off, so 2026 is the only untouched data: change nothing after seeing its results.

Run from the ml-service folder:
    python -m training.train                    # all events (~40 min)
    python -m training.train --events rain hot  # retrain only some events
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.tree import DecisionTreeClassifier

from training.prepare_dataset import EVENTS
from training.prepare_dataset import OUTPUT as DATASET

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
BUNDLE = MODELS_DIR / "clearcast_models.joblib"
REPORT = MODELS_DIR / "evaluation_report.json"

NON_FEATURES = ["timestamp", "location", "split", *EVENTS]

# Evaluated for the report, but too rare in ERA5 to predict, so not offered as a user alert
REPORT_ONLY_EVENTS = ["storm"]

# Acceptance criteria from proposal section 3.2.4
TARGET_RECALL = 0.85
TARGET_F1 = 0.80
# The "likely" cut-off is set for 90% recall on the validation year, a safety margin so
# recall stays above the 85% target on unseen years.
LIKELY_VAL_RECALL = 0.90
# When ClearCast says "very likely", it should come true at least this often
VERY_LIKELY_PRECISION = 0.80

# Model -> hyperparameter grid. class_weight="balanced" stops the model from ignoring
# rare events such as storms. Each forest tree sees a 25% sample, which keeps training fast.
CANDIDATES = {
    "random_forest": (
        RandomForestClassifier(
            n_estimators=60, max_samples=0.25, class_weight="balanced", n_jobs=-1, random_state=42
        ),
        {"max_depth": [10, 16], "min_samples_leaf": [10, 50]},
    ),
    "decision_tree": (
        DecisionTreeClassifier(class_weight="balanced", random_state=42),
        {"max_depth": [6, 10, 14], "min_samples_leaf": [20, 100]},
    ),
}

# Documented flood periods inside the test years, for the operational check
FLOOD_PERIODS = [
    ("2023 El Nino short rains", "Kisumu", "2023-10-15", "2023-12-31"),
    ("2023 El Nino short rains", "Mombasa", "2023-11-01", "2023-11-30"),
    ("2024 long-rains floods", "Nairobi", "2024-04-01", "2024-05-31"),
]


def band_cutoffs(y_val, p_val):
    """Probability cut-offs for the four likelihood bands, set on the validation year."""
    precision, recall, thresholds = precision_recall_curve(y_val, p_val)
    precision, recall = precision[:-1], recall[:-1]  # align with thresholds
    # likely: the highest cut-off that still catches >= 90% of real events
    likely = float(thresholds[recall >= LIKELY_VAL_RECALL].max())
    # very likely: the lowest cut-off above that where >= 80% of warnings come true
    reached = (thresholds >= likely) & (precision >= VERY_LIKELY_PRECISION)
    very_likely = float(thresholds[reached].min()) if reached.any() else (likely + 1) / 2
    return {
        "unlikely": likely / 2,
        "likely": likely,
        "very_likely": very_likely,
        "very_likely_precision_reached": bool(reached.any()),
    }


def evaluate(y, p, cutoffs):
    """Test-set metrics. An alert counts as raised when the band is "likely" or above."""
    alert = p >= cutoffs["likely"]
    return {
        "positives": int(y.sum()),
        "accuracy": accuracy_score(y, alert),
        "precision": precision_score(y, alert, zero_division=0),
        "recall": recall_score(y, alert, zero_division=0),
        "f1": f1_score(y, alert, zero_division=0),
        "auc_roc": roc_auc_score(y, p) if y.nunique() == 2 else None,
        "very_likely_precision": precision_score(y, p >= cutoffs["very_likely"], zero_division=0),
    }


def baseline_predictions(df, event):
    """Simple rules the models should beat: "the same as N hours ago".

    A label from N hours ago only uses hours already known now. flood_risk looks 24 h ahead,
    so its label is not known until 24 h later.
    """
    past = df.sort_values("timestamp").groupby("location")[event]
    return {f"same_as_{h}h_ago": past.shift(h) == 1 for h in ([24] if event == "flood_risk" else [6, 24])}


def evaluate_baselines(baselines, d, event):
    rows = {}
    for name, alert in baselines.items():
        y, a = d[event], alert.loc[d.index]
        rows[name] = {
            "precision": precision_score(y, a, zero_division=0),
            "recall": recall_score(y, a, zero_division=0),
            "f1": f1_score(y, a, zero_division=0),
        }
    return rows


def flood_check(test, p_test, cutoff):
    """Share of real flood-risk hours in documented flood periods that ClearCast flagged."""
    rows = []
    for name, loc, start, end in FLOOD_PERIODS:
        mask = (test.location == loc) & test.timestamp.between(start, end) & (test.flood_risk == 1)
        caught = (p_test[mask.to_numpy()] >= cutoff).mean() if mask.any() else None
        rows.append({"period": name, "location": loc, "flood_hours": int(mask.sum()), "caught": caught})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Train and evaluate ClearCast's event models")
    ap.add_argument("--events", nargs="+", choices=EVENTS, default=EVENTS)
    args = ap.parse_args()

    print(f"Loading {DATASET} ...")
    df = pd.read_csv(DATASET, parse_dates=["timestamp"])
    features = [c for c in df.columns if c not in NON_FEATURES]
    train = df[df.split == "train"].sort_values("timestamp")  # time order for TimeSeriesSplit
    val = df[df.split == "val"]
    test = df[df.split == "test"]
    final = df[df.split == "final"]
    X_train, X_val, X_test, X_final = (d[features].astype("float32") for d in (train, val, test, final))
    cv = TimeSeriesSplit(n_splits=5)  # each fold validates on data later than it trained on

    MODELS_DIR.mkdir(exist_ok=True)
    bundle = joblib.load(BUNDLE) if BUNDLE.exists() and args.events != EVENTS else {"events": {}}
    report = json.loads(REPORT.read_text()) if REPORT.exists() and args.events != EVENTS else {}
    bundle.update(
        version=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M"),
        features=features,
        sklearn_version=sklearn.__version__,  # models must be loaded with this same version
    )

    for event in args.events:
        print(f"\n=== {event} ===")
        results = {}
        for name, (estimator, grid) in CANDIDATES.items():
            search = GridSearchCV(estimator, grid, cv=cv, scoring="average_precision")
            search.fit(X_train, train[event])
            p_val = search.predict_proba(X_val)[:, 1]
            results[name] = {
                "model": search.best_estimator_,
                "params": search.best_params_,
                "cv_ap": search.best_score_,
                "val_ap": average_precision_score(val[event], p_val),
                "p_val": p_val,
            }
            print(f"  {name:14s} {search.best_params_}  CV AP={search.best_score_:.3f}  "
                  f"val AP={results[name]['val_ap']:.3f}")

        winner = max(results, key=lambda n: results[n]["val_ap"])
        best = results[winner]
        cutoffs = band_cutoffs(val[event], best["p_val"])
        p_test = best["model"].predict_proba(X_test)[:, 1]
        metrics = evaluate(test[event], p_test, cutoffs)
        metrics["meets_targets"] = metrics["recall"] >= TARGET_RECALL and metrics["f1"] >= TARGET_F1
        p_final = best["model"].predict_proba(X_final)[:, 1]
        final_metrics = evaluate(final[event], p_final, cutoffs)
        final_metrics["meets_targets"] = final_metrics["recall"] >= TARGET_RECALL and final_metrics["f1"] >= TARGET_F1
        baselines = baseline_predictions(df, event)
        importances = pd.Series(best["model"].feature_importances_, index=features).nlargest(5)

        if event not in REPORT_ONLY_EVENTS:
            bundle["events"][event] = {
                "model": best["model"],
                "model_type": winner,
                "explainer": results["decision_tree"]["model"],  # readable rules for admins
                "cutoffs": cutoffs,
            }
        report[event] = {
            "model_type": winner,
            "comparison": {n: {k: r[k] for k in ("params", "cv_ap", "val_ap")} for n, r in results.items()},
            "cutoffs": cutoffs,
            "test": metrics,
            "final": final_metrics,
            "baselines": {
                "test": evaluate_baselines(baselines, test, event),
                "final": evaluate_baselines(baselines, final, event),
            },
            "top_features": importances.round(3).to_dict(),
        }
        if event == "flood_risk":
            report[event]["flood_periods"] = flood_check(test, p_test, cutoffs["likely"])

        print(f"  winner: {winner} | test recall={metrics['recall']:.2f} precision={metrics['precision']:.2f} "
              f"F1={metrics['f1']:.2f} AUC={metrics['auc_roc']:.3f} | "
              f"{'MEETS' if metrics['meets_targets'] else 'below'} targets")

    joblib.dump(bundle, BUNDLE, compress=3)
    REPORT.write_text(json.dumps(report, indent=2, default=float))
    print_summary(report)


def results_table(report, split):
    rows = {
        e: {
            "model": r["model_type"],
            "positives": r[split]["positives"],
            "recall": r[split]["recall"],
            "precision": r[split]["precision"],
            "f1": r[split]["f1"],
            "auc_roc": r[split]["auc_roc"],
            "very_likely_prec": r[split]["very_likely_precision"],
            "meets_targets": r[split]["meets_targets"],
        }
        for e, r in report.items()
    }
    table = pd.DataFrame(rows).T
    numeric = ["recall", "precision", "f1", "auc_roc", "very_likely_prec"]
    table[numeric] = table[numeric].astype(float).round(3)
    return table


def baseline_table(report, split):
    rows = {
        f"{e} / {name}": {k: round(v, 3) for k, v in metrics.items()}
        for e, r in report.items()
        for name, metrics in r["baselines"][split].items()
    }
    return pd.DataFrame(rows).T


def print_summary(report):
    print(f"\nTest results 2023-2025 (alert = 'likely' or above), saved to {REPORT}:")
    print(results_table(report, "test").to_string())
    print("\nFinal holdout results 2026 (alert = 'likely' or above):")
    print(results_table(report, "final").to_string())
    print("\nBaseline rules, test 2023-2025:")
    print(baseline_table(report, "test").to_string())
    print("\nBaseline rules, final holdout 2026:")
    print(baseline_table(report, "final").to_string())
    if "flood_risk" in report:
        print("\nOperational check - documented flood periods:")
        for row in report["flood_risk"]["flood_periods"]:
            caught = "n/a" if row["caught"] is None else f"{100 * row['caught']:.0f}%"
            print(f"  {row['period']}, {row['location']}: {row['flood_hours']} flood-risk hours, {caught} flagged")
    print(f"\nModels saved to {BUNDLE}")


if __name__ == "__main__":
    main()
