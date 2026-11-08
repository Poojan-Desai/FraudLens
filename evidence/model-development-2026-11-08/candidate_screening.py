"""Development-only screening; never creates/evaluates a final holdout.

Run with FraudLens' venv and PYTHONPATH pointing to its repository. All output is
confined to this directory. The predeclared protocol is written before fitting.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits
from xgboost import XGBClassifier

from backend.app.ml.experiment import FEATURES
from backend.app.ml.synthetic import generate_transactions
from backend.app.ml.train import _preprocessor


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parent / "repos" / "FraudLens"
SEEDS = (11, 29, 73)
BOUNDARIES = (0, 45_000, 56_250, 63_750)
EXPECTED_FEATURES = [
    "amount", "merchant_category", "country", "distance_from_home",
    "transactions_last_hour", "average_amount_30d", "amount_to_customer_average",
    "new_device", "card_present", "account_age_days", "is_international", "previous_declines",
]
assert FEATURES == EXPECTED_FEATURES, "Original feature allowlist changed; stop for review."

BASE_PARAMETERS = dict(
    learning_rate=0.05, subsample=0.85, colsample_bytree=0.85,
    objective="binary:logistic", eval_metric="aucpr", n_jobs=1,
)


def candidate(name, weight, depth, estimators, **parameters):
    return {"id": name, "weight_rule": weight, "parameters": {
        **BASE_PARAMETERS, "max_depth": depth, "n_estimators": estimators, **parameters,
    }}


# Written once to the protocol before any fit or metric is computed.
CANDIDATES = [
    candidate("baseline_existing", "negative_positive_ratio", 3, 300),
    candidate("unit_d3_300_default", "one", 3, 300),
    candidate("sqrt_d3_300_default", "sqrt_negative_positive_ratio", 3, 300),
    *[
        candidate(f"unit_d{depth}_{estimators}_regularized", "one", depth, estimators,
                  min_child_weight=5, reg_lambda=5)
        for depth in (2, 3, 4) for estimators in (300, 600)
    ],
    *[
        candidate(f"sqrt_d{depth}_600_regularized", "sqrt_negative_positive_ratio", depth, 600,
                  min_child_weight=5, reg_lambda=5)
        for depth in (2, 3, 4)
    ],
]
assert len(CANDIDATES) == 12


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path, value, *, exclusive=False):
    with path.open("x" if exclusive else "w") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def safe_parameters(parameters):
    return {key: "nan" if isinstance(value, float) and not math.isfinite(value) else value
            for key, value in parameters.items()}


def metrics(labels, probability):
    assert np.isfinite(probability).all()
    budget = math.floor(0.02 * len(labels))
    # Fixed budget, no probability threshold tuning. Ties prefer earlier rows.
    selected = np.argsort(-probability, kind="stable")[:budget]
    found = int(labels[selected].sum())
    positives = int(labels.sum())
    return {
        "average_precision": float(average_precision_score(labels, probability)),
        "recall_at_top_2_percent": found / positives,
        "precision_at_top_2_percent": found / budget,
        "top_2_percent_budget": budget,
        "top_2_percent_true_positives": found,
        "top_2_percent_false_positives": budget - found,
        "selection_positives": positives,
        "selection_rows": len(labels),
        "brier_score": float(brier_score_loss(labels, probability)),
        "roc_auc": float(roc_auc_score(labels, probability)),
    }


def main():
    if (ROOT / "candidate-screen-results.json").exists():
        raise FileExistsError("Completed screen already exists; do not overwrite or expand the grid.")
    provenance = {
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {name: version(name) for name in
                     ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "joblib", "threadpoolctl")},
        "repository_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True).strip(),
        "source_sha256": {name: hashlib.sha256((REPOSITORY / name).read_bytes()).hexdigest() for name in
                          ("backend/app/ml/experiment.py", "backend/app/ml/train.py", "backend/app/ml/synthetic.py")},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    protocol = {
        "schema": "fraudlens-development-screen/v1", "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_rows_per_seed": 75_000, "development_seeds": list(SEEDS),
        "used_rows": {"train": 45_000, "calibration": 11_250, "selection": 7_500},
        "boundary_indices": list(BOUNDARIES),
        "unused_rows": "Rows 63750:75000 are discarded without inspection, prediction, evaluation or selection use.",
        "features": FEATURES, "feature_changes": "None; no target, timestamp, metadata or derived-rule features.",
        "preprocessing": "Unchanged repository _preprocessor, fitted on training rows only for each candidate.",
        "calibration": "Unchanged sigmoid CalibratedClassifierCV(FrozenEstimator(pipeline)), fitted on calibration rows only.",
        "estimator_random_state": "Equal to that development seed, as in the existing baseline.",
        "ranking": ["mean selection average_precision_score across the three seeds",
                    "mean selection recall at a fixed top-2-percent budget (150 of 7500), as secondary tie break",
                    "candidate ID, ascending, for exact ties"],
        "candidate_grid": CANDIDATES, "provenance": provenance,
        "scope": "Development model selection only; no final holdout generated or inspected. No real-payment claim.",
    }
    protocol_bytes = canonical(protocol)
    write_json(ROOT / "protocol-v1.json", protocol, exclusive=True)
    results = {"protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(), "status": "in_progress",
               "provenance": provenance, "development_windows": [], "fits": []}
    total_started = time.perf_counter()
    with threadpool_limits(limits=1):
        for seed in SEEDS:
            # Generating 75000 is required to keep the original RNG process.
            # Retain only the development prefix; never split/validate/inspect
            # the remaining test window or invoke the full experiment runner.
            generated = generate_transactions(75_000, seed=seed)
            development = generated.iloc[:BOUNDARIES[-1]].copy()
            del generated
            parts = {name: development.iloc[start:end].copy()
                     for name, start, end in zip(("train", "calibration", "selection"), BOUNDARIES, BOUNDARIES[1:])}
            for name, part in parts.items():
                assert len(part) == protocol["used_rows"][name]
                assert part.is_fraud.nunique() == 2
                assert part.timestamp.is_monotonic_increasing
            assert parts["train"].timestamp.max() < parts["calibration"].timestamp.min()
            assert parts["calibration"].timestamp.max() < parts["selection"].timestamp.min()
            results["development_windows"].append({
                "seed": seed,
                "development_prefix_sha256": hashlib.sha256(development.to_csv(index=False, lineterminator="\n").encode()).hexdigest(),
                "windows": {name: {"rows": len(part), "positives": int(part.is_fraud.sum()),
                                    "start": part.timestamp.min().isoformat(), "end": part.timestamp.max().isoformat()}
                            for name, part in parts.items()},
            })
            train, calibration, selection = (parts[name] for name in ("train", "calibration", "selection"))
            ratio = float((~train.is_fraud).sum() / train.is_fraud.sum())
            selection_labels = selection.is_fraud.to_numpy().astype(int)
            predictions = {"labels": selection_labels}
            for config in CANDIDATES:
                weight = {"negative_positive_ratio": ratio, "sqrt_negative_positive_ratio": math.sqrt(ratio), "one": 1.0}[config["weight_rule"]]
                estimator = XGBClassifier(**config["parameters"], scale_pos_weight=weight, random_state=seed)
                pipeline = Pipeline([("preprocess", _preprocessor(FEATURES)), ("model", estimator)])
                started = time.perf_counter()
                pipeline.fit(train[FEATURES], train.is_fraud)
                trained = time.perf_counter()
                calibrated = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid", n_jobs=1)
                calibrated.fit(calibration[FEATURES], calibration.is_fraud)
                calibrated_at = time.perf_counter()
                probability = calibrated.predict_proba(selection[FEATURES])[:, 1]
                values = metrics(selection_labels, probability)
                fit = {"candidate": config["id"], "seed": seed, "resolved_parameters": safe_parameters(estimator.get_params()),
                       "metrics": values, "timing_seconds": {"fit": trained - started,
                       "sigmoid_calibration": calibrated_at - trained, "total_with_selection_prediction": time.perf_counter() - started}}
                results["fits"].append(fit)
                predictions[config["id"]] = probability
                write_json(ROOT / "progress.json", results)
                print(json.dumps({"candidate": config["id"], "seed": seed, "selection_ap": values["average_precision"],
                                  "recall_top_2_percent": values["recall_at_top_2_percent"], "seconds": fit["timing_seconds"]["total_with_selection_prediction"]}), flush=True)
            # Selection predictions only: no test predictions are produced.
            np.savez_compressed(ROOT / f"selection-predictions-seed-{seed}.npz", **predictions)
            del development, parts, train, calibration, selection, predictions
    aggregate = []
    for config in CANDIDATES:
        fits = [item for item in results["fits"] if item["candidate"] == config["id"]]
        assert {item["seed"] for item in fits} == set(SEEDS)
        aps = [item["metrics"]["average_precision"] for item in fits]
        recalls = [item["metrics"]["recall_at_top_2_percent"] for item in fits]
        aggregate.append({"candidate": config["id"], "mean_selection_ap": statistics.mean(aps),
                          "selection_ap_sample_standard_deviation": statistics.stdev(aps),
                          "mean_selection_recall_top_2_percent": statistics.mean(recalls),
                          "selection_recall_sample_standard_deviation": statistics.stdev(recalls),
                          "per_seed": [{"seed": item["seed"], **item["metrics"]} for item in fits],
                          "total_fit_calibration_predict_seconds": sum(item["timing_seconds"]["total_with_selection_prediction"] for item in fits)})
    aggregate.sort(key=lambda item: (-item["mean_selection_ap"], -item["mean_selection_recall_top_2_percent"], item["candidate"]))
    winner = aggregate[0]
    baseline = next(item for item in aggregate if item["candidate"] == "baseline_existing")
    recommendation = next(config for config in CANDIDATES if config["id"] == winner["candidate"])
    results.update({"status": "complete", "aggregate_ranking": aggregate, "frozen_recommendation": recommendation,
                    "development_comparison": {"baseline_mean_selection_ap": baseline["mean_selection_ap"],
                     "candidate_mean_selection_ap": winner["mean_selection_ap"],
                     "absolute_ap_delta": winner["mean_selection_ap"] - baseline["mean_selection_ap"],
                     "relative_ap_change": winner["mean_selection_ap"] / baseline["mean_selection_ap"] - 1,
                     "baseline_mean_recall_top_2_percent": baseline["mean_selection_recall_top_2_percent"],
                     "candidate_mean_recall_top_2_percent": winner["mean_selection_recall_top_2_percent"]},
                    "elapsed_seconds": time.perf_counter() - total_started,
                    "limitations": ["Selection outcomes are development evidence used to choose among 12 predeclared configurations.",
                                    "Three synthetic seeds are not independent real-payment external validation or a significance guarantee.",
                                    "The remaining test windows were neither inspected nor evaluated. No final holdout was generated.",
                                    "Primary selection AP can disagree with fixed-budget recall; both are retained.",
                                    "No generator-rule feature engineering, data alteration, test-based tuning or production model publication occurred."]})
    write_json(ROOT / "candidate-screen-results.json", results, exclusive=True)
    write_json(ROOT / "frozen-candidate.json", {"protocol_sha256": results["protocol_sha256"], "candidate": recommendation,
               "selection_criterion": protocol["ranking"], "development_seeds": list(SEEDS), "features": FEATURES,
               "preprocessing": protocol["preprocessing"], "calibration": protocol["calibration"],
               "provenance": provenance, "status": "proposal frozen before any final holdout evaluation"}, exclusive=True)
    lines = ["# FraudLens development-only candidate recommendation", "",
             f"Frozen proposal: **{recommendation['id']}**.", "",
             f"Mean selection AP: baseline {baseline['mean_selection_ap']:.6f}; candidate {winner['mean_selection_ap']:.6f}.",
             f"Mean selection recall at 150 / 7500 reviews: baseline {baseline['mean_selection_recall_top_2_percent']:.6f}; candidate {winner['mean_selection_recall_top_2_percent']:.6f}.", "",
             "| Candidate | Mean selection AP | AP sample SD | Mean recall @ top 2% |", "| --- | ---: | ---: | ---: |"]
    lines.extend(f"| {item['candidate']} | {item['mean_selection_ap']:.6f} | {item['selection_ap_sample_standard_deviation']:.6f} | {item['mean_selection_recall_top_2_percent']:.6f} |" for item in aggregate)
    lines.extend(["", "## Exact candidate", "", "```json", json.dumps(recommendation, indent=2), "```", "",
                  "This is development model selection, not a final result. The candidate was chosen by mean selection AP across development seeds 11, 29 and 73, with mean selection recall at a fixed top-2% budget as the secondary tie break. Sigmoid calibration uses a separate 11,250-row calibration window. Original feature allowlist and preprocessing are unchanged. Only training/calibration/selection data were retained. Remaining test rows were discarded without inspection. No final holdout was generated or inspected.", "",
                  "The full JSON retains per-seed results, resolved parameters, timing, source hashes and versions. A controlled fresh holdout must compare the frozen baseline and proposal under a frozen protocol before any stronger model-improvement claim. No real-world fraud-detection or bank-savings claim follows from this screen."])
    (ROOT / "candidate-screen-recommendation.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": "complete", "winner": recommendation["id"], **results["development_comparison"],
                      "elapsed_seconds": results["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
