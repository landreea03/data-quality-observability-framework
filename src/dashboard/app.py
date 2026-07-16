"""
Streamlit dashboard: health score over time + drill-down into any run.

    streamlit run src/dashboard/app.py
"""
import sys
from pathlib import Path

# Streamlit runs this file directly (not as a module), so the project root
# isn't on sys.path by default -- add it so `from src import ...` resolves
# regardless of which directory `streamlit run` was launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import select

from src import config
from src.db.engine import get_engine, get_session
from src.db.models import DQCheckResult, DQRunSummary

st.set_page_config(page_title="Data Quality Observability", layout="wide")

engine = get_engine()
session = get_session(engine)

st.title("Data Quality Observability Dashboard")
st.caption(f"Table: `{config.TABLE_NAME}`")

summaries = session.execute(
    select(DQRunSummary).where(DQRunSummary.table_name == config.TABLE_NAME).order_by(DQRunSummary.run_date)
).scalars().all()

if not summaries:
    st.warning("No pipeline runs found yet. Run `python -m scripts.run_pipeline --date YYYY-MM-DD` or `python -m scripts.demo` first.")
    st.stop()

summary_df = pd.DataFrame([{
    "run_date": s.run_date, "health_score": s.health_score, "status": s.status,
    "passed_checks": s.passed_checks, "total_checks": s.total_checks,
} for s in summaries])

latest = summary_df.iloc[-1]
col1, col2, col3 = st.columns(3)
col1.metric("Latest health score", f"{latest['health_score']}/100")
col2.metric("Latest status", latest["status"])
col3.metric("Checks passed", f"{int(latest['passed_checks'])}/{int(latest['total_checks'])}")

st.subheader("Health score over time")
st.line_chart(summary_df.set_index("run_date")["health_score"])

st.subheader("Inspect a specific run")
selected_date = st.selectbox("Run date", options=list(reversed(summary_df["run_date"].tolist())))

check_rows = session.execute(
    select(DQCheckResult).where(
        DQCheckResult.table_name == config.TABLE_NAME,
        DQCheckResult.run_date == selected_date,
    )
).scalars().all()

check_df = pd.DataFrame([{
    "check": c.check_name, "column": c.column_name or "-", "passed": c.passed,
    "severity": c.severity, "metric": c.metric_value, "baseline_mean": c.baseline_mean,
    "baseline_std": c.baseline_std, "message": c.message,
} for c in check_rows])


def _highlight(row):
    return ["background-color: #ffe1e1" if not row["passed"] else ""] * len(row)


st.dataframe(check_df.style.apply(_highlight, axis=1), use_container_width=True)

st.subheader("Null rate trend per column")
null_checks = session.execute(
    select(DQCheckResult).where(
        DQCheckResult.table_name == config.TABLE_NAME,
        DQCheckResult.check_name == "nulls",
    )
).scalars().all()
null_df = pd.DataFrame([{"run_date": c.run_date, "column": c.column_name, "null_rate": c.metric_value} for c in null_checks])
if not null_df.empty:
    pivot = null_df.pivot_table(index="run_date", columns="column", values="null_rate")
    st.line_chart(pivot)

st.subheader("Row volume trend")
volume_checks = session.execute(
    select(DQCheckResult).where(
        DQCheckResult.table_name == config.TABLE_NAME,
        DQCheckResult.check_name == "volume",
    )
).scalars().all()
volume_df = pd.DataFrame([{"run_date": c.run_date, "row_count": c.metric_value} for c in volume_checks])
if not volume_df.empty:
    st.line_chart(volume_df.set_index("run_date")["row_count"])

session.close()
