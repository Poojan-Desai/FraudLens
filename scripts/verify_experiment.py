"""Run from repository root: PYTHONPATH=. python scripts/verify_experiment.py RUN_DIR."""
import argparse
import json
from pathlib import Path

from backend.app.ml.verify import verify_study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify hashes and recompute held-out evidence without loading model pickles")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_study(args.run_dir), indent=2))
    except (ValueError, KeyError, OSError, TypeError) as error:
        raise SystemExit(f"Evidence verification failed: {error}") from error
