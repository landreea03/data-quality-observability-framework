import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Order(Base):
    """Landed warehouse copy of each day's orders batch, tagged with load_date
    so the check engine can pull a rolling window of history per column."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, nullable=True)
    customer_id = Column(String, nullable=True)
    product_id = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    order_date = Column(String, nullable=True)
    status = Column(String, nullable=True)
    load_date = Column(Date, nullable=False, index=True)


class DQRunSummary(Base):
    """One row per (table, run_date) -- the health score shown on the dashboard."""

    __tablename__ = "dq_run_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    run_date = Column(Date, nullable=False, index=True)
    total_checks = Column(Integer, nullable=False)
    passed_checks = Column(Integer, nullable=False)
    health_score = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # healthy / degraded / unhealthy
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (UniqueConstraint("table_name", "run_date", name="uq_dq_run_summary_table_date"),)


class DQCheckResult(Base):
    """One row per individual check per run -- what the dashboard drill-down reads."""

    __tablename__ = "dq_check_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    run_date = Column(Date, nullable=False, index=True)
    check_name = Column(String, nullable=False)
    column_name = Column(String, nullable=True)
    passed = Column(Boolean, nullable=False)
    severity = Column(String, nullable=False)  # low / medium / high
    metric_value = Column(Float, nullable=True)
    baseline_mean = Column(Float, nullable=True)
    baseline_std = Column(Float, nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
