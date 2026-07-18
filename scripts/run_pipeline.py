"""
Standalone pipeline runner -- loads one day's CSV into Postgres, runs the
DataQualityEngine, persists results, and alerts Slack if unhealthy.

This is what the Airflow DAG calls under the hood, and it also works
completely on its own (no Airflow required) for local development and demos:

    python -m scripts.run_pipeline --date 2026-07-12
"""
import argparse
import math
from datetime import date

import pandas as pd

from src import config
from src.alerts.slack import send_alert
from src.checks.engine import DataQualityEngine
from src.db.engine import get_engine, get_session, init_db
from src.db.models import Order


def _clean(value):
    """Normalize a pandas cell value before it hits the database.

    Two problems this avoids: (1) pandas represents a missing/nulled CSV
    cell as float NaN even in a text column (e.g. a nulled customer_id),
    and handing that raw NaN to psycopg2 for a VARCHAR column causes a
    binding/type error on Postgres that sqlite silently tolerates; (2)
    pandas returns numpy scalar types (int64, float64) which are safest
    converted to native Python types before going to the DB driver.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):  # numpy scalar, e.g. numpy.int64 / numpy.float64
        value = value.item()
    return value


def load_csv_to_db(session, run_date: date) -> pd.DataFrame:
    path = config.DATA_DIR / f"orders_{run_date.isoformat()}.csv"
    df = pd.read_csv(path)

    # Idempotent re-runs: clear any rows already loaded for this date.
    session.query(Order).filter(Order.load_date == run_date).delete()

    for _, row in df.iterrows():
        session.add(Order(
            order_id=_clean(row.get("order_id")),
            customer_id=_clean(row.get("customer_id")) if "customer_id" in df.columns else None,
            product_id=_clean(row.get("product_id")) if "product_id" in df.columns else None,
            price=_clean(row.get("price")) if "price" in df.columns else None,
            quantity=_clean(row.get("quantity")) if "quantity" in df.columns else None,
            order_date=_clean(row.get("order_date")) if "order_date" in df.columns else None,
            status=_clean(row.get("status")) if "status" in df.columns else None,
            load_date=run_date,
        ))
    session.commit()
    return df


def run_for_date(run_date: date, dry_run_slack: bool = False, alert_threshold: float = config.HEALTH_SCORE_UNHEALTHY_THRESHOLD) -> dict:
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)

    df = load_csv_to_db(session, run_date)

    dq_engine = DataQualityEngine(session)
    run_output = dq_engine.run(df, run_date)
    dq_engine.persist(run_output)

    print(f"[{run_date}] health_score={run_output['health_score']} status={run_output['status']} "
          f"({run_output['passed_checks']}/{run_output['total_checks']} checks passed)")
    for r in run_output["results"]:
        flag = "OK  " if r.passed else "FAIL"
        col = f" [{r.column_name}]" if r.column_name else ""
        print(f"  [{flag}] {r.check_name}{col}: {r.message}")

    if run_output["health_score"] < alert_threshold:
        send_alert(run_output, dry_run=dry_run_slack)

    session.close()
    return run_output


def main():
    parser = argparse.ArgumentParser(description="Run the data quality pipeline for one date")
    parser.add_argument("--date", required=True)
    parser.add_argument("--dry-run-slack", action="store_true", help="print the Slack message instead of sending it")
    args = parser.parse_args()
    run_for_date(date.fromisoformat(args.date), dry_run_slack=args.dry_run_slack)


if __name__ == "__main__":
    main()
