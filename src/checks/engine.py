"""
DataQualityEngine -- the project's brain.

Given today's freshly-loaded DataFrame and a run_date, pulls a rolling
window of history from Postgres, runs every check against that baseline,
computes a 0-100 health score, and persists both the summary and the
per-check detail so the dashboard can render trends over time.
"""
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select

from src import config
from src.checks.categorical_drift import check_categorical_drift
from src.checks.distribution import check_distribution
from src.checks.duplicates import check_duplicates
from src.checks.freshness import check_freshness
from src.checks.nulls import check_nulls
from src.checks.schema import check_schema
from src.checks.volume import check_volume
from src.db.models import DQCheckResult, DQRunSummary, Order


class DataQualityEngine:
    def __init__(self, session, table_name: str = config.TABLE_NAME):
        self.session = session
        self.table_name = table_name

    def _historical_orders(self, run_date: date, window_days: int = config.BASELINE_WINDOW_DAYS) -> pd.DataFrame:
        start = run_date - timedelta(days=window_days)
        stmt = select(Order).where(Order.load_date >= start, Order.load_date < run_date)
        rows = self.session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame(columns=["order_id", "customer_id", "product_id", "price", "quantity", "order_date", "status", "load_date"])
        return pd.DataFrame([{
            "order_id": r.order_id, "customer_id": r.customer_id, "product_id": r.product_id,
            "price": r.price, "quantity": r.quantity, "order_date": r.order_date,
            "status": r.status, "load_date": r.load_date,
        } for r in rows])

    def run(self, today_df: pd.DataFrame, run_date: date) -> dict:
        historical_df = self._historical_orders(run_date)
        results = []

        results.append(check_freshness(today_df))

        daily_counts = historical_df.groupby("load_date").size().tolist() if not historical_df.empty else []
        results.append(check_volume(len(today_df), daily_counts))

        results.extend(check_schema(set(today_df.columns), set(config.EXPECTED_SCHEMA.keys())))

        nullable_columns = [c for c in config.EXPECTED_SCHEMA if c != "order_date"]
        for col in nullable_columns:
            if not historical_df.empty and col in historical_df.columns:
                hist_rates = historical_df.groupby("load_date")[col].apply(lambda s: s.isna().mean()).tolist()
            else:
                hist_rates = []
            results.append(check_nulls(today_df, col, hist_rates))

        for col in config.NUMERIC_COLUMNS:
            if not historical_df.empty and col in historical_df.columns:
                hist_means = historical_df.groupby("load_date")[col].apply(lambda s: s.dropna().mean()).dropna().tolist()
            else:
                hist_means = []
            results.append(check_distribution(today_df, col, hist_means))

        history_days = historical_df["load_date"].nunique() if not historical_df.empty else 0
        for col in config.CATEGORICAL_COLUMNS:
            hist_for_col = historical_df if history_days >= config.MIN_HISTORY_DAYS else historical_df.iloc[0:0]
            results.append(check_categorical_drift(today_df, col, hist_for_col))

        results.append(check_duplicates(today_df, key_columns=["order_id"]))

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        health_score = round(100 * passed / total, 1) if total else 100.0
        if health_score == 100:
            status = "healthy"
        elif health_score >= 80:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "run_date": run_date,
            "results": results,
            "total_checks": total,
            "passed_checks": passed,
            "health_score": health_score,
            "status": status,
        }

    def persist(self, run_output: dict) -> None:
        run_date = run_output["run_date"]

        # Idempotent re-runs: clear any prior results for this (table, date) first.
        self.session.query(DQRunSummary).filter_by(table_name=self.table_name, run_date=run_date).delete()
        self.session.query(DQCheckResult).filter_by(table_name=self.table_name, run_date=run_date).delete()

        self.session.add(DQRunSummary(
            table_name=self.table_name,
            run_date=run_date,
            total_checks=run_output["total_checks"],
            passed_checks=run_output["passed_checks"],
            health_score=run_output["health_score"],
            status=run_output["status"],
        ))

        for r in run_output["results"]:
            self.session.add(DQCheckResult(
                table_name=self.table_name,
                run_date=run_date,
                check_name=r.check_name,
                column_name=r.column_name,
                passed=r.passed,
                severity=r.severity,
                # Defensively cast to native Python float: numpy.float64 values
                # (which pandas/numpy operations can silently produce) break
                # psycopg2's SQL parameter binding, even though sqlite accepts
                # them fine -- this guards against that regardless of which
                # check produced the number.
                metric_value=float(r.metric_value) if r.metric_value is not None else None,
                baseline_mean=float(r.baseline_mean) if r.baseline_mean is not None else None,
                baseline_std=float(r.baseline_std) if r.baseline_std is not None else None,
                message=r.message,
            ))

        self.session.commit()
