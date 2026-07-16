# Data Quality Observability Framework

A mini Monte Carlo / Great Expectations: a statistical observability layer
that sits on top of a daily data pipeline and catches schema drift, null
spikes, volume anomalies, and distribution shifts automatically — without
hand-tuned thresholds — then alerts Slack and shows a health-score trend
on a dashboard.

Simulated dataset: a daily `orders` batch (`order_id`, `customer_id`,
`product_id`, `price`, `quantity`, `order_date`, `status`), standing in
for a real e-commerce ingestion pipeline.

## Architecture

```
generator.py (fake daily batch)  --or-->  corrupt.py (inject failure on demand)
              |
              v
   Airflow DAG (daily @ orders_data_quality)
              |
              v
   load into Postgres `orders` table (tagged with load_date)
              |
              v
   DataQualityEngine  <-- pulls rolling 14-day baseline per column
     - freshness   - volume (z-score)      - schema drift
     - nulls (5x baseline spike)           - distribution shift (z-score)
     - duplicates
              |
              v
   dq_run_summary / dq_check_results tables in Postgres
              |
       +------+------+
       v             v
  Streamlit        Slack webhook
  dashboard        (only fires if health score < 90)
```

The statistical core lives in `src/checks/` — each check compares today's
metric against a rolling mean/std computed from the prior 7–14 days, so no
column needs a manually hardcoded threshold. `src/checks/engine.py` is the
orchestrator that ties them together into one health score per run.

## Project layout

```
src/
  config.py            thresholds, DB URL, expected schema
  generator.py          fake daily orders batch generator
  corrupt.py             CLI to inject nulls / dropped columns / volume drops / price spikes / dupes
  db/
    models.py            SQLAlchemy models: orders, dq_run_summary, dq_check_results
    engine.py             engine/session factory
  checks/
    freshness.py, volume.py, schema.py, nulls.py, distribution.py, duplicates.py
    engine.py             DataQualityEngine: runs all checks, computes health score, persists
  alerts/
    slack.py              incoming-webhook alerting (falls back to dry-run print)
  dashboard/
    app.py                Streamlit health-score dashboard
airflow/
  dags/orders_dq_dag.py   daily DAG: generate -> maybe corrupt -> load & check
  Dockerfile              Airflow image + our requirements.txt
scripts/
  run_pipeline.py         standalone runner for one date (what Airflow calls)
  demo.py                 the 60-second demo: 11 clean days + 1 corrupted day
tests/
  test_checks.py          unit tests for every check's detection logic
docker-compose.yml        Postgres (app data) + Postgres (Airflow metadata) + Airflow webserver/scheduler
```

## Quickstart — local demo (no Docker/Airflow required)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# For the fastest local run, edit .env and set:
# DATABASE_URL=sqlite:///data/dq_framework.db

export $(cat .env | xargs)   # or use python-dotenv / direnv

python -m pytest tests/ -v          # unit tests for the detection logic
python -m scripts.demo              # 11 clean days + day 12 corrupted, printed to console
streamlit run src/dashboard/app.py  # view the health-score trend + drill-down
```

`scripts/demo.py` is the entire "day-12 corruption" story end to end: it
generates 11 healthy days to build a baseline, then injects a 40%
`customer_id` null spike, a 95% volume drop, and a price distribution
spike all on day 12 — and prints exactly which checks failed and by how
much (this ran successfully in testing: health score dropped from 100 to
66.7/100, flagging the volume drop, null spike, and price shift by name).

## Full stack — Postgres + Airflow + Slack via Docker

```bash
cp .env.example .env   # fill in SLACK_WEBHOOK_URL (see below) and leave DATABASE_URL pointed at Postgres
docker compose up --build
```

- Airflow UI: http://localhost:8080 (user: `admin` / pass: `admin`)
- Turn on the `orders_data_quality` DAG — it runs daily and will backfill nothing (`catchup=False`)
- To demo a failure on a specific date: Airflow UI -> Admin -> Variables ->
  add `dq_corrupt_today` = the target run date (e.g. `2026-06-12`), then
  trigger that day's DAG run. The `maybe_inject_corruption` task will
  corrupt the data before the check task runs.
- Dashboard against the same Postgres: `streamlit run src/dashboard/app.py`
  with `DATABASE_URL` pointed at `localhost:5433`.

### Setting up the Slack webhook

1. https://api.slack.com/apps -> **Create New App** -> **From scratch**
2. Pick your workspace, name it e.g. "Data Quality Bot"
3. Left sidebar -> **Incoming Webhooks** -> toggle on
4. **Add New Webhook to Workspace** -> choose a channel (e.g. `#data-alerts`)
5. Copy the webhook URL and put it in `.env` as `SLACK_WEBHOOK_URL=...`

Without a webhook set, `send_alert()` prints the message to stdout instead
of failing — so the whole pipeline still runs end to end.

## How the statistical logic works (no hardcoded thresholds)

- **Volume**: z-score of today's row count against the mean/std of the
  last 14 days; flags if `|z| > 3`.
- **Nulls**: flags if today's null rate exceeds `max(baseline * 5, 2%)` —
  the 5x multiplier catches real spikes while the 2% floor avoids false
  positives on columns that are normally almost never null.
- **Distribution**: z-score of today's column mean against the rolling
  mean/std of daily means; flags if `|z| > 3`.
- **Categorical drift**: Population Stability Index (PSI) on the `status`
  column — the same technique risk/ML teams use in production to detect
  when a categorical column's *shape* shifts (e.g. a payment bug suddenly
  spiking the refund rate), which a mean/std check on numeric columns
  can't see. PSI < 0.10 is stable, 0.10–0.25 is a moderate shift worth a
  look, ≥0.25 is flagged as a real problem.
- **Schema**: diff of today's column set against the expected schema;
  flags missing or unexpected columns.
- **Duplicates**: flags if the duplicate rate on the natural key exceeds 1%.
- All statistical checks require **7 days of history** before activating
  (`MIN_HISTORY_DAYS`), so a cold-start pipeline doesn't false-alarm on day one.

Each run computes a health score: `100 * passed_checks / total_checks`.
≥90 is healthy, 80–89 is degraded, below that is unhealthy (and triggers Slack).

## For your resume / interviews

This is the story to tell: *"I built a system that automatically detects
when upstream data breaks — using rolling statistical baselines and a
Population Stability Index check (the same drift-detection technique
production ML/risk teams use) instead of hardcoded thresholds — and I can
show a specific day where I injected a null spike, volume drop, price
distribution shift, and a refund-rate spike simultaneously, and the
system caught all four, scored that day unhealthy, and would have
alerted Slack within minutes."*

Suggested next step: record a 60–90 second screen capture of
`python -m scripts.demo` followed by the dashboard showing the red dot on
day 12 — that clip is what goes in your portfolio/resume link.

## Possible extensions (if you have time before interviews)

- Swap the fixed z-score threshold for a seasonal model (e.g. day-of-week
  aware baselines, since real e-commerce volume dips on weekends)
- Add a `--table` flag so the engine can watch more than one pipeline
- Swap hand-rolled checks for Great Expectations expectations as the
  check-writing layer, keeping this project's orchestration/storage/alerting
