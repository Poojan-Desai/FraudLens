from pathlib import Path

from sklearn.datasets import fetch_openml

from backend.app.ml.validation import validate_schema


if __name__ == "__main__":
    output = Path("data/raw/creditcard.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset = fetch_openml(data_id=1597, as_frame=True, parser="auto")
    frame = dataset.frame.rename(columns={dataset.target.name: "Class"}) if dataset.target.name != "Class" else dataset.frame
    validate_schema(frame, "real")
    frame.to_csv(output, index=False)
    print(f"Validated and wrote {len(frame):,} OpenML benchmark transactions to {output}")
