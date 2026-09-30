import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)  # so `from api...` / `from analysis...` work when run directly

import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from analysis.analyse_fights import (
    load_fights_into_sqlite, get_completed_fight_ids, load_fight_result,
)
from api.Fights import PUNCH_TYPE_FIELDS, COUNTER_FIELD

CORNER_FEATURE_NAMES = (
    "total_thrown", "total_landed", "accuracy", "power_landed", "power_share",
    "head_landed", "body_landed", "counter_landed", "knocked_down",
)

def _round_corner_features(punches: dict, knocked_down: int) -> dict:
    """Summarise one corner's punch stats for one round into a flat dict."""
    total_thrown = sum(punches[f]["thrown"] for f in PUNCH_TYPE_FIELDS)
    total_landed = sum(punches[f]["landed"] for f in PUNCH_TYPE_FIELDS)
    accuracy = (total_landed / total_thrown) if total_thrown else 0.0
    power_landed = punches["power"]["landed"]
    power_share = (power_landed / total_landed) if total_landed else 0.0

    return {
        "total_thrown": total_thrown,
        "total_landed": total_landed,
        "accuracy": accuracy,
        "power_landed": power_landed,
        "power_share": power_share,
        "head_landed": punches["head"]["landed"],
        "body_landed": punches["body"]["landed"],
        "counter_landed": punches[COUNTER_FIELD]["landed"],
        "knocked_down": knocked_down,
    }

def build_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    One row per (fight, judge, round) with a real score for both corners
    """
    rows = []

    for fight_id in get_completed_fight_ids(conn):
        result = load_fight_result(fight_id)
        scorecards = result.get("scorecards") or {}
        rounds = result.get("rounds") or {}
        red_rounds = rounds.get("red_corner") or []
        blue_rounds = rounds.get("blue_corner") or []

        for judge, corners in scorecards.items():
            red_scores = corners.get("red_corner", [])
            blue_scores = corners.get("blue_corner", [])

            for i, (red_score, blue_score) in enumerate(zip(red_scores, blue_scores)):
                if red_score is None or blue_score is None:
                    continue  # unscored (the stoppage round and beyond)
                if i >= len(red_rounds) or i >= len(blue_rounds):
                    continue  # defensive -- shouldn't happen with valid data

                red_feat = _round_corner_features(
                    red_rounds[i]["punches"], red_rounds[i]["knocked_down"]
                )
                blue_feat = _round_corner_features(
                    blue_rounds[i]["punches"], blue_rounds[i]["knocked_down"]
                )

                if red_score > blue_score:
                    winner = "red"
                elif blue_score > red_score:
                    winner = "blue"
                else:
                    winner = "even"

                row = {"FightID": fight_id, "Judge": judge, "RoundNumber": i + 1, "Winner": winner}
                for name in CORNER_FEATURE_NAMES:
                    row[f"red_{name}"] = red_feat[name]
                    row[f"blue_{name}"] = blue_feat[name]
                    row[f"diff_{name}"] = red_feat[name] - blue_feat[name]
                rows.append(row)

    return pd.DataFrame(rows)


def main():
    conn = sqlite3.connect(":memory:")
    load_fights_into_sqlite(conn)
    df = build_dataset(conn)
    conn.close()

    if df.empty:
        print("No scored rounds found yet -- nothing to train on.")
        return

    feature_columns = [c for c in df.columns if c not in ("FightID", "Judge", "RoundNumber", "Winner")]
    X, y, groups = df[feature_columns], df["Winner"], df["FightID"]

    print(f"Dataset: {len(df)} scored (fight, judge, round) rows from {groups.nunique()} fight(s).")
    print("Label distribution:")
    print(y.value_counts().to_string())

    n_fights = groups.nunique()
    if n_fights < 2:
        print(
            "\nOnly one fight in the dataset -- can't hold out a fight-level test set. "
            "Fitting on everything and evaluating on the same data as a sanity check only; "
            "treat any accuracy number below as meaningless until there's more data."
        )
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
        train_idx, test_idx = next(splitter.split(X, y, groups))
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        print(
            f"\nTrain: {len(X_train)} rows from {groups.iloc[train_idx].nunique()} fights. "
            f"Test: {len(X_test)} rows from {groups.iloc[test_idx].nunique()} fights. "
            f"(split by FightID -- no fight's rounds appear on both sides)"
        )

    model = Pipeline([
        ("scale", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=1000)),
    ])
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    # Baseline: whoever landed more total punches wins the round, else even.
    # If the trained model can't beat this, it hasn't learned anything a single raw stat didn't already tell you.
    baseline_pred = np.where(
        X_test["diff_total_landed"] > 0, "red",
        np.where(X_test["diff_total_landed"] < 0, "blue", "even"),
    )
    baseline_accuracy = accuracy_score(y_test, baseline_pred)

    print(f"\nModel accuracy:    {accuracy:.2%}")
    print(f"Baseline accuracy: {baseline_accuracy:.2%}  (predict winner = whoever landed more total punches)")

    labels = sorted(y.unique())
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    print("\nConfusion matrix (rows = actual, columns = predicted):")
    print("        " + "".join(f"{lbl:>8}" for lbl in labels))
    for lbl, row_counts in zip(labels, cm):
        print(f"{lbl:<8}" + "".join(f"{c:>8}" for c in row_counts))

    # ---- Feature weights ----
    logreg = model.named_steps["logreg"]
    class_labels = list(logreg.classes_)
    coefs = logreg.coef_  # (n_classes, n_features) for 3+ classes; (1, n_features) if only 2 showed up

    print("\nFeature weights (on STANDARDISED features, so magnitudes are comparable across features):")
    if coefs.shape[0] == 1:
        # Only two classes were present in the training data -- one row of log-odds for class_labels[1] vs. class_labels[0].
        print(f"\n  Predicting '{class_labels[1]}' vs. '{class_labels[0]}':")
        ranked = sorted(zip(feature_columns, coefs[0]), key=lambda item: abs(item[1]), reverse=True)
        for name, weight in ranked[:10]:
            print(f"    {name:<20}{weight:+.3f}")
    else:
        for class_label, class_coefs in zip(class_labels, coefs):
            print(f"\n  Predicting '{class_label}':")
            ranked = sorted(zip(feature_columns, class_coefs), key=lambda item: abs(item[1]), reverse=True)
            for name, weight in ranked[:10]:
                print(f"    {name:<20}{weight:+.3f}")

    mean_abs = np.mean(np.abs(coefs), axis=0)
    ranked_overall = sorted(zip(feature_columns, mean_abs), key=lambda item: item[1], reverse=True)
    print("\nOverall feature importance (mean absolute weight across classes):")
    for name, weight in ranked_overall:
        print(f"  {name:<20}{weight:.3f}")

if __name__ == "__main__":
    main()
