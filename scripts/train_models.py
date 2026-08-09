from pathlib import Path

import pandas as pd

from backend.app.ml.train import train_logistic, train_xgboost


if __name__ == "__main__":
    source = Path("data/synthetic/transactions.csv")
    if not source.exists():
        raise SystemExit("Run scripts/generate_synthetic.py first")
    frame = pd.read_csv(source, parse_dates=["timestamp"])
    print(train_logistic(frame, Path("artifacts")))
    print(train_xgboost(frame, Path("artifacts")))
