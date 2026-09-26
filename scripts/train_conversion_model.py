"""
train_conversion_model.py
Trains and evaluates lead-conversion classifiers on a real, public dataset
(X Education "Lead Scoring", ~9,240 leads with a Converted 0/1 outcome) and
writes a JSON report that the Trust page renders.

Also re-runs the message-scoring benchmark so both results sit in one report.

Usage:
    pip install -r requirements-ml.txt
    python -m scripts.train_conversion_model            # downloads the CSV on first run
    python -m scripts.train_conversion_model --csv path/to/Leads.csv
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from scripts.paths import ROOT_DIR, data_dir

# Mirror of the Kaggle dataset (subset of columns: the behavioural signals a CRM
# records for every lead). Original: kaggle.com/datasets/amritachatterjee09/lead-scoring-dataset
DATASET_URL = "https://raw.githubusercontent.com/prajwalpr11/lead_score/HEAD/leads.csv"
DATASET_NAME = "X Education lead scoring (Kaggle)"
REPORT_PATH = ROOT_DIR / "evaluation" / "models" / "conversion-model.json"

TARGET = "Converted"
NUMERIC = ["TotalVisits", "Total Time Spent on Website", "Page Views Per Visit"]
CATEGORICAL = ["Lead Source", "Last Activity"]
TEST_SHARE = 0.25
SEED = 42
THRESHOLD = 0.5
MIN_CATEGORY_COUNT = 30
ROC_POINTS = 40
CALIBRATION_BINS = 10
TOP_SHARES = (0.1, 0.2, 0.3, 0.5)
PERMUTATION_REPEATS = 5
DOWNLOAD_TIMEOUT_S = 60


def load_dataset(csv_path: Path | None) -> pd.DataFrame:
    path = csv_path or data_dir() / "datasets" / "x-education-leads.csv"
    if not path.exists():
        print(f"[*] Downloading dataset to {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        resp = httpx.get(DATASET_URL, timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [c for c in [TARGET, *NUMERIC, *CATEGORICAL] if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset is missing columns: {', '.join(missing)}")
    return df[[TARGET, *NUMERIC, *CATEGORICAL]]


def preprocessor(scale: bool) -> ColumnTransformer:
    numeric_steps = [("impute", SimpleImputer(strategy="median"))]
    if scale:
        numeric_steps.append(("scale", StandardScaler()))
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
        ("onehot", OneHotEncoder(
            handle_unknown="infrequent_if_exist", min_frequency=MIN_CATEGORY_COUNT, sparse_output=False
        )),
    ])
    return ColumnTransformer([("num", Pipeline(numeric_steps), NUMERIC), ("cat", categorical, CATEGORICAL)])


def candidates() -> Dict[str, Dict[str, Any]]:
    return {
        "baseline": {
            "label": "Always guess 'not converted'",
            "model": Pipeline([("prep", preprocessor(False)), ("clf", DummyClassifier(strategy="prior"))]),
        },
        "logistic_regression": {
            "label": "Logistic regression",
            "model": Pipeline([("prep", preprocessor(True)), ("clf", LogisticRegression(max_iter=2000))]),
        },
        "gradient_boosting": {
            "label": "Gradient boosting",
            "model": Pipeline([
                ("prep", preprocessor(False)),
                ("clf", HistGradientBoostingClassifier(random_state=SEED, max_iter=300, learning_rate=0.05)),
            ]),
        },
    }


def classification_metrics(y_true: np.ndarray, proba: np.ndarray) -> Dict[str, Any]:
    pred = (proba >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    single_class = len(np.unique(proba)) == 1
    return {
        "accuracy": round(accuracy_score(y_true, pred), 4),
        "precision": round(precision_score(y_true, pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, pred, zero_division=0), 4),
        "roc_auc": 0.5 if single_class else round(roc_auc_score(y_true, proba), 4),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def roc_points(y_true: np.ndarray, proba: np.ndarray) -> List[Dict[str, float]]:
    fpr, tpr, _ = roc_curve(y_true, proba)
    idx = np.unique(np.linspace(0, len(fpr) - 1, ROC_POINTS).astype(int))
    return [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in idx]


def calibration(y_true: np.ndarray, proba: np.ndarray) -> List[Dict[str, Any]]:
    edges = np.linspace(0, 1, CALIBRATION_BINS + 1)
    bins = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (proba >= lo) & ((proba < hi) if hi < 1 else (proba <= hi))
        if mask.sum():
            bins.append({
                "predicted": round(float(proba[mask].mean()), 4),
                "actual": round(float(y_true[mask].mean()), 4),
                "count": int(mask.sum()),
            })
    return bins


def lift(y_true: np.ndarray, proba: np.ndarray) -> List[Dict[str, float]]:
    """Share of all conversions captured if sales only calls the top-scored X% of leads."""
    order = np.argsort(-proba)
    total = y_true.sum()
    rows = []
    for share in TOP_SHARES:
        top = order[: max(1, int(len(order) * share))]
        rows.append({
            "top_share": share,
            "conversions_captured": round(float(y_true[top].sum() / total), 4),
            "conversion_rate": round(float(y_true[top].mean()), 4),
        })
    return rows


def feature_importance(model: Pipeline, x_test: pd.DataFrame, y_test: np.ndarray) -> List[Dict[str, Any]]:
    result = permutation_importance(
        model, x_test, y_test, scoring="roc_auc", n_repeats=PERMUTATION_REPEATS, random_state=SEED
    )
    rows = [
        {"feature": name, "importance": round(float(mean), 4)}
        for name, mean in zip(x_test.columns, result.importances_mean)
    ]
    return sorted(rows, key=lambda r: r["importance"], reverse=True)


def conversion_by(df: pd.DataFrame, column: str, limit: int = 8) -> List[Dict[str, Any]]:
    grouped = df.groupby(df[column].fillna("Unknown"))[TARGET].agg(["count", "mean"])
    grouped = grouped[grouped["count"] >= MIN_CATEGORY_COUNT].sort_values("count", ascending=False).head(limit)
    return [
        {"value": str(idx), "leads": int(row["count"]), "conversion_rate": round(float(row["mean"]), 4)}
        for idx, row in grouped.iterrows()
    ]


def message_benchmark() -> Dict[str, Any] | None:
    try:
        from scripts.run_evaluation import run_benchmarks
        return run_benchmarks()
    except Exception as err:  # the report is still useful without it
        print(f"[WARN] Message benchmark skipped: {err}", file=sys.stderr)
        return None


def train(csv_path: Path | None) -> Dict[str, Any]:
    df = load_dataset(csv_path)
    x, y = df[NUMERIC + CATEGORICAL], df[TARGET].to_numpy()
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=TEST_SHARE, stratify=y, random_state=SEED)

    models = []
    fitted = {}
    for key, spec in candidates().items():
        spec["model"].fit(x_train, y_train)
        proba = spec["model"].predict_proba(x_test)[:, 1]
        fitted[key] = (spec["model"], proba)
        models.append({"key": key, "label": spec["label"], **classification_metrics(y_test, proba)})
        print(f"[*] {spec['label']:<30} AUC {models[-1]['roc_auc']:.3f}  accuracy {models[-1]['accuracy']:.3f}")

    best_key = max((m for m in models if m["key"] != "baseline"), key=lambda m: m["roc_auc"])["key"]
    best_model, best_proba = fitted[best_key]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "name": DATASET_NAME,
            "rows": int(len(df)),
            "train_rows": int(len(x_train)),
            "test_rows": int(len(x_test)),
            "conversion_rate": round(float(y.mean()), 4),
            "features": NUMERIC + CATEGORICAL,
        },
        "threshold": THRESHOLD,
        "best_model": best_key,
        "models": models,
        "roc": {key: roc_points(y_test, proba) for key, (_, proba) in fitted.items() if key != "baseline"},
        "calibration": calibration(y_test, best_proba),
        "lift": lift(y_test, best_proba),
        "feature_importance": feature_importance(best_model, x_test, y_test),
        "conversion_by_source": conversion_by(df, "Lead Source"),
        "message_benchmark": message_benchmark(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, help="Local copy of the lead scoring CSV")
    args = parser.parse_args()
    report = train(args.csv)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[PASS] Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
