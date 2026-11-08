"""Freeze, evaluate once, or verify a paired independent synthetic comparison."""
import argparse
import json
from pathlib import Path
from backend.app.ml.model_comparison import Candidate, ComparisonPlan, freeze_plan, run_comparison, verify_comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--candidate", type=Path, required=True)
    freeze.add_argument("--development-report", type=Path, required=True)
    freeze.add_argument("--protocol", type=Path, required=True)
    freeze.add_argument("--plan", type=Path, required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--plan", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("run", type=Path)
    verify.add_argument("--evidence-only", action="store_true", help="Explicitly verify prediction metrics/source data without checking unprovided model bundles")
    args = parser.parse_args()
    if args.command == "freeze":
        proposed = json.loads(args.candidate.read_text())["candidate"]
        development = json.loads(args.development_report.read_text())
        if development.get("status") != "complete" or development.get("frozen_recommendation") != proposed:
            raise ValueError("proposal must match the completed development recommendation")
        ranked = sorted(development["aggregate_ranking"], key=lambda row: (-row["mean_selection_ap"], row["candidate"]))
        if ranked[0]["candidate"] != proposed["id"]:
            raise ValueError("proposal must maximize mean development AP")
        params = proposed["parameters"]
        fixed = {"learning_rate": .05, "subsample": .85, "colsample_bytree": .85,
                 "objective": "binary:logistic", "eval_metric": "aucpr", "n_jobs": 1}
        if any(params.get(key) != value for key, value in fixed.items()) or set(params) - {*fixed, "max_depth", "n_estimators", "min_child_weight", "reg_lambda"}:
            raise ValueError("proposal differs from supported fixed model family")
        spec = Candidate(id=proposed["id"], weight_rule=proposed["weight_rule"], max_depth=params["max_depth"], n_estimators=params["n_estimators"], min_child_weight=params.get("min_child_weight", 1), reg_lambda=params.get("reg_lambda", 1))
        frozen = freeze_plan(args.plan, ComparisonPlan(candidate=spec), args.development_report, args.protocol)
        print(json.dumps({"plan_id": frozen["plan_id"], "frozen_at_utc": frozen["frozen_at_utc"], "final_data_generated": False}, indent=2))
    elif args.command == "evaluate":
        report = run_comparison(args.plan, args.output)
        print(json.dumps({"plan_id": report["plan_id"], "models": report["models"], "comparison": report["comparison"]}, indent=2))
    else:
        print(json.dumps(verify_comparison(args.run, require_models=not args.evidence_only), indent=2))


if __name__ == "__main__":
    main()
