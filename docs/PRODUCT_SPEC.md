# Product Spec: Data Quality Observability Framework

**Author:** Andreea Alexandra
**Status:** Shipped (v1), evaluating v2 scope
**Related:** [Live demo](https://data-quality-observability-framework-png9f54d5pele4hmuxdr4w.streamlit.app/) · [Repo](https://github.com/landreea03/data-quality-observability-framework)

## Problem

Data pipelines fail silently. A source starts sending nulls where it used to send values, a column gets renamed upstream without notice, a row count drops 98% because a job failed halfway through, a price field starts reporting in the wrong currency — and in every one of these cases, the pipeline itself reports success. Nothing crashes. The first signal anyone gets is usually a business stakeholder asking why a dashboard or model looks wrong, days after the underlying data broke. This gap between "the pipeline ran" and "the data is actually correct" is often called data downtime, and it's expensive enough that it's spawned an entire vendor category (Monte Carlo, Bigeye, Great Expectations) selling exactly this capability to data teams.

Most teams below a certain size never buy or build this. They either have no automated data quality checks at all, or they have a handful of hardcoded thresholds a data engineer wrote once ("alert if row count < 1000") that go stale the moment the business grows or seasonality shifts, generating either false alarms or silence at the worst possible time.

## Who this is for

A data or analytics engineer who owns one or more scheduled pipelines feeding a warehouse, and who currently has no automated way to know a pipeline "succeeded" but produced bad data. Secondary audience: an engineering manager or data platform lead evaluating whether to buy a vendor tool or build a lightweight in-house equivalent for a small number of critical tables.

## Goals

The system should tell an operator, within one pipeline run of a failure, that something is statistically abnormal about today's data, specifically enough that they know where to look without manually diffing the data themselves. It should do this without per-column manual threshold tuning, since threshold tuning is the reason most homegrown data quality scripts get abandoned within a few months.

## Non-goals (v1)

This is not a general-purpose data catalog or lineage tool, it does not attempt root-cause analysis (it tells you *what* changed, not *why*), and it does not support arbitrary user-defined tables in its current form — v1 is scoped to a single simulated `orders` table to prove out the detection methodology end to end before generalizing.

## Success metrics

For the demo pipeline, the system should catch 100% of injected failure types (null spike, volume drop, schema drift, distribution shift, categorical drift, duplicate spike) within the same run they're introduced, with zero false positives across 11 consecutive days of clean baseline data. In a real deployment, the metrics that would actually matter are mean time to detection (currently: one pipeline run, i.e. typically under 24 hours) and false-positive rate per week (currently untuned against real production variance, since this runs against simulated data — this is the biggest open risk, discussed below).

## Solution summary

A statistical check engine computes a rolling baseline (mean, standard deviation, or category proportions, depending on check type) from the prior 7–14 days of data per column, then flags today's run if it deviates beyond a threshold: a z-score above 3 for numeric checks, a 5x baseline multiplier for null rates, and a Population Stability Index above 0.25 for categorical distribution shifts. Every run gets a 0–100 health score and is logged to Postgres; a Streamlit dashboard shows the trend and lets someone drill into exactly which check failed and by how much; a Slack alert fires automatically when the score drops below 90. Airflow orchestrates the daily run in the full deployment; a standalone script does the same job without requiring Airflow for local development and demos.

## Key risks and tradeoffs

The single biggest risk in taking this from demo to production is false-positive rate: a fixed z-score threshold of 3 works cleanly against a fixed, artificially stable simulated distribution, but real production data has real seasonality (weekday vs. weekend order volume, holiday spikes) that a naive rolling baseline would misread as an anomaly. The README already flags this as the top v2 candidate: a day-of-week-aware or seasonally decomposed baseline instead of a flat rolling window. A second risk is the 7-day cold-start period, during which the system can't statistically evaluate anything and a real failure during that window would go undetected — acceptable for a demo, not acceptable for a production launch without a fallback (e.g., hardcoded sane bounds during cold start). Third, this v1 watches exactly one table; generalizing to N tables means the check engine, not just the config, needs to become table-agnostic, which is a real refactor, not a config change.

## Rollout plan (if this were a real internal tool)

Phase 1 would run in shadow mode: checks run and log to the dashboard, but Slack alerts are suppressed, for two to four weeks, purely to calibrate what "normal" noise looks like against real data and tune the false-positive rate before anyone's pager depends on it. Phase 2 turns on Slack alerts for a single high-value pipeline, with an explicit feedback loop (a reaction emoji or short form) for the on-call engineer to mark an alert as a true or false positive, feeding back into threshold tuning. Phase 3 generalizes the engine to additional tables based on demand, prioritizing tables that have previously caused a "why do these numbers look weird" incident.
