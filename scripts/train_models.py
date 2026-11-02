"""Compatibility entry point for the supported four-window synthetic study."""
import sys

from scripts.run_experiment import main as run_study


def main() -> None:
    print(
        "Deprecated: train_models.py now runs the four-window study with the "
        "same --config, --output and --snapshot options as run_experiment.py. "
        "It generates the configured synthetic dataset; legacy "
        "data/synthetic/transactions.csv is not loaded. Use "
        "PYTHONPATH=. python scripts/run_experiment.py for new runs.",
        file=sys.stderr,
    )
    run_study()


if __name__ == "__main__":
    main()
