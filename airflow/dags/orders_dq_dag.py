"""
Data Quality Observability DAG for the `orders` pipeline.

Each daily run:
  1. Generates that day's orders batch (stand-in for a real upstream landing zone)
  2. Optionally injects corruption if the `dq_corrupt_today` Airflow Variable
     matches today's run date -- this is how you demo a failure on schedule
  3. Loads it into the dq-postgres warehouse
  4. Runs the statistical data quality engine against a rolling baseline
  5. Persists results and alerts Slack if the health score drops below threshold

To DEMO a failure via Airflow:
  Admin -> Variables -> add `dq_corrupt_today` = 2026-06-12 (or whatever
  run date you want to break), then trigger/wait for that day's DAG run.
"""
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/opt/airflow")

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator


def _generate(**context):
    from datetime import date as _date

    from src.generator import generate_day, save_day

    run_date = _date.fromisoformat(context["ds"])
    df = generate_day(run_date, n_rows=5000, seed=abs(hash(context["ds"])) % 100000)
    save_day(df, run_date)


def _maybe_corrupt(**context):
    corrupt_date = Variable.get("dq_corrupt_today", default_var="")
    if corrupt_date != context["ds"]:
        return

    import pandas as pd

    from src import config
    from src.corrupt import apply_null_rate, apply_price_spike, apply_volume_scale

    path = config.DATA_DIR / f"orders_{corrupt_date}.csv"
    df = pd.read_csv(path)
    df = apply_null_rate(df, "customer_id", 0.4)
    df = apply_volume_scale(df, 0.05)
    df = apply_price_spike(df, 0.1)
    df.to_csv(path, index=False)


def _run_pipeline(**context):
    from datetime import date as _date

    from scripts.run_pipeline import run_for_date

    run_for_date(_date.fromisoformat(context["ds"]))


default_args = {
    "owner": "data-eng",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="orders_data_quality",
    description="Daily ingestion + automated data quality checks for the orders table",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["data-quality", "orders"],
) as dag:
    generate = PythonOperator(task_id="generate_daily_batch", python_callable=_generate)
    maybe_corrupt = PythonOperator(task_id="maybe_inject_corruption", python_callable=_maybe_corrupt)
    run_checks = PythonOperator(task_id="load_and_run_quality_checks", python_callable=_run_pipeline)

    generate >> maybe_corrupt >> run_checks
