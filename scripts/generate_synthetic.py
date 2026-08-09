from pathlib import Path

from backend.app.ml.synthetic import generate_transactions


if __name__ == "__main__":
    output = Path("data/synthetic/transactions.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_transactions()
    frame.to_csv(output, index=False)
    print(f"Wrote {len(frame):,} clearly labeled synthetic transactions to {output}")
