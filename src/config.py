import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

# Load variables from a .env file at the project root (if present) into the
# environment, so DATABASE_URL / SLACK_WEBHOOK_URL set there are picked up
# automatically without you having to `export` them by hand every time.
load_dotenv(BASE_DIR / ".env")

# Points at the docker-compose "dq-postgres" service by default. Override with
# env var DATABASE_URL for local testing (e.g. a sqlite file).
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    os.environ.get("DQ_DATABASE_URL", "postgresql+psycopg2://dq_user:dq_pass@localhost:5433/dq_framework"),
)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

TABLE_NAME = "orders"

# --- Statistical baseline settings ---
BASELINE_WINDOW_DAYS = 14          # how many days of history to compute rolling stats over
MIN_HISTORY_DAYS = 7               # minimum days of history required before statistical checks activate
Z_SCORE_THRESHOLD = 3.0            # flag if |z-score| exceeds this
NULL_RATE_SPIKE_MULTIPLIER = 5.0   # flag if today's null rate > baseline * this multiplier
NULL_RATE_FLOOR = 0.02             # minimum baseline null rate assumed, avoids div-by-near-zero false positives
HEALTH_SCORE_UNHEALTHY_THRESHOLD = 90  # below this score, trigger a Slack alert

NUMERIC_COLUMNS = ["price", "quantity"]
CATEGORICAL_COLUMNS = ["status"]  # checked for distribution drift via PSI

EXPECTED_SCHEMA = {
    "order_id": "int",
    "customer_id": "str",
    "product_id": "str",
    "price": "float",
    "quantity": "int",
    "order_date": "str",
    "status": "str",
}
