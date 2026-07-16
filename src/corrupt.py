"""
Corruption injector -- simulates the real-world ways upstream pipelines
silently break, so the data quality engine has something to catch:

    --null-rate customer_id=0.4     40% of customer_id becomes null
    --drop-column customer_id       column disappears entirely (schema drift)
    --volume-scale 0.05             only 5% of the normal row count lands
    --price-spike 0.1               10% of rows get a $50k-$200k price (bad unit/currency bug)
    --duplicate-rate 0.2            20% of rows get duplicated
    --status-shift refunded=0.3     30% of rows get force-shifted to 'refunded' (e.g. a payment bug)

Run this *after* src.generator has produced the day's CSV; it edits the
file in place so the "landed" data looks exactly like a real failure.
"""
import argparse

import numpy as np
import pandas as pd

from src import config


def apply_null_rate(df: pd.DataFrame, column: str, rate: float) -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    mask = np.random.rand(len(df)) < rate
    df.loc[mask, column] = None
    return df


def apply_drop_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    return df.drop(columns=[column], errors="ignore")


def apply_volume_scale(df: pd.DataFrame, scale: float) -> pd.DataFrame:
    n = max(1, int(len(df) * scale))
    return df.sample(n=n, random_state=42).reset_index(drop=True)


def apply_price_spike(df: pd.DataFrame, fraction: float, spike_min: float = 50000, spike_max: float = 200000) -> pd.DataFrame:
    df = df.copy()
    if "price" not in df.columns:
        return df
    n = max(1, int(len(df) * fraction))
    idx = np.random.choice(df.index, size=n, replace=False)
    df.loc[idx, "price"] = np.random.uniform(spike_min, spike_max, size=n)
    return df


def apply_status_shift(df: pd.DataFrame, target_status: str, rate: float) -> pd.DataFrame:
    """Force-shifts a fraction of rows to a given status, simulating a
    categorical distribution shift (e.g. a payment processor bug suddenly
    causing a spike in refunds) that PSI is designed to catch."""
    df = df.copy()
    if "status" not in df.columns:
        return df
    eligible = df.index[df["status"] != target_status]
    if len(eligible) == 0:
        return df
    n = max(1, min(len(eligible), int(len(df) * rate)))
    idx = np.random.choice(eligible, size=n, replace=False)
    df.loc[idx, "status"] = target_status
    return df


def apply_duplicate_rows(df: pd.DataFrame, fraction: float) -> pd.DataFrame:
    n = max(1, int(len(df) * fraction))
    dup = df.sample(n=n, random_state=7)
    return pd.concat([df, dup], ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Inject data quality problems into a generated daily CSV")
    parser.add_argument("--date", required=True)
    parser.add_argument("--null-rate", action="append", default=[], metavar="COLUMN=RATE")
    parser.add_argument("--drop-column", action="append", default=[])
    parser.add_argument("--volume-scale", type=float, default=None)
    parser.add_argument("--price-spike", type=float, default=None, help="fraction of rows to spike")
    parser.add_argument("--duplicate-rate", type=float, default=None)
    parser.add_argument("--status-shift", action="append", default=[], metavar="STATUS=RATE")
    args = parser.parse_args()

    path = config.DATA_DIR / f"orders_{args.date}.csv"
    df = pd.read_csv(path)

    for spec in args.null_rate:
        column, rate = spec.split("=")
        df = apply_null_rate(df, column, float(rate))
        print(f"Injected {float(rate) * 100:.1f}% nulls into '{column}'")

    for column in args.drop_column:
        df = apply_drop_column(df, column)
        print(f"Dropped column '{column}'")

    if args.volume_scale is not None:
        original = len(df)
        df = apply_volume_scale(df, args.volume_scale)
        print(f"Scaled volume from {original} to {len(df)} rows")

    if args.price_spike is not None:
        df = apply_price_spike(df, args.price_spike)
        print(f"Injected price spikes into {args.price_spike * 100:.1f}% of rows")

    if args.duplicate_rate is not None:
        original = len(df)
        df = apply_duplicate_rows(df, args.duplicate_rate)
        print(f"Added duplicates: {original} -> {len(df)} rows")

    for spec in args.status_shift:
        target_status, rate = spec.split("=")
        df = apply_status_shift(df, target_status, float(rate))
        print(f"Shifted {float(rate) * 100:.1f}% of rows to status='{target_status}'")

    df.to_csv(path, index=False)
    print(f"Saved corrupted data -> {path}")


if __name__ == "__main__":
    main()
