"""
The 60-second demo: simulates 11 clean days of the 'orders' pipeline
(building up a healthy baseline), then corrupts day 12 with a
customer_id null spike, a 95% volume drop, a price distribution spike,
and a refund-rate spike (categorical drift via PSI) all at once --
and shows the engine catching every one of them.

    python -m scripts.demo
"""
import subprocess
import sys
from datetime import date, timedelta

from scripts.run_pipeline import run_for_date

START_DATE = date(2026, 6, 1)
N_CLEAN_DAYS = 11


def sh(cmd: list) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    order_id_counter = 1

    for i in range(N_CLEAN_DAYS):
        run_date = START_DATE + timedelta(days=i)
        sh([sys.executable, "-m", "src.generator", "--date", run_date.isoformat(),
            "--rows", "5000", "--seed", str(1000 + i), "--start-order-id", str(order_id_counter)])
        order_id_counter += 5000
        run_for_date(run_date, dry_run_slack=True)
        print("-" * 80)

    corrupt_date = START_DATE + timedelta(days=N_CLEAN_DAYS)
    sh([sys.executable, "-m", "src.generator", "--date", corrupt_date.isoformat(),
        "--rows", "5000", "--seed", "9999", "--start-order-id", str(order_id_counter)])
    sh([sys.executable, "-m", "src.corrupt", "--date", corrupt_date.isoformat(),
        "--null-rate", "customer_id=0.4",
        "--volume-scale", "0.05",
        "--price-spike", "0.1",
        "--status-shift", "refunded=0.3"])

    print(f"\n=== DAY 12 ({corrupt_date}) -- CORRUPTED DATA ===")
    run_for_date(corrupt_date, dry_run_slack=True)


if __name__ == "__main__":
    main()
