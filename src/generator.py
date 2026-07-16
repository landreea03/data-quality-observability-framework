"""
Fake daily 'orders' batch generator.

Simulates what a real e-commerce ingestion pipeline would drop into a
landing zone each day: order_id, customer_id, product_id, price, quantity,
order_date, status. Row counts and price distribution are randomized
around fixed, realistic parameters so that 11+ consecutive days look like
a stable, healthy pipeline -- which is exactly the baseline the data
quality engine needs before it can tell "normal" from "broken".
"""
import argparse
import random
from datetime import date
from pathlib import Path

import pandas as pd

from src import config

STATUS_WEIGHTS = ["completed"] * 90 + ["cancelled"] * 5 + ["refunded"] * 5


def generate_day(run_date: date, n_rows: int = 5000, seed: int | None = None, start_order_id: int = 1) -> pd.DataFrame:
    rng = random.Random(seed)
    customer_pool = [f"C-{i:04d}" for i in range(1, 1001)]
    product_pool = [f"P-{i:03d}" for i in range(1, 201)]

    rows = []
    for i in range(n_rows):
        price = round(max(5.0, min(500.0, rng.normalvariate(87.0, 45.0))), 2)
        rows.append({
            "order_id": start_order_id + i,
            "customer_id": rng.choice(customer_pool),
            "product_id": rng.choice(product_pool),
            "price": price,
            "quantity": rng.randint(1, 5),
            "order_date": run_date.isoformat(),
            "status": rng.choice(STATUS_WEIGHTS),
        })
    return pd.DataFrame(rows)


def save_day(df: pd.DataFrame, run_date: date) -> Path:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DATA_DIR / f"orders_{run_date.isoformat()}.csv"
    df.to_csv(path, index=False)
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate a fake daily orders batch")
    parser.add_argument("--date", required=True, help="Run date, YYYY-MM-DD")
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--start-order-id", type=int, default=1)
    args = parser.parse_args()

    run_date = date.fromisoformat(args.date)
    df = generate_day(run_date, n_rows=args.rows, seed=args.seed, start_order_id=args.start_order_id)
    path = save_day(df, run_date)
    print(f"Generated {len(df)} rows for {run_date} -> {path}")


if __name__ == "__main__":
    main()
