"""
Slack incoming-webhook alerting.

Setup (one-time):
  1. Go to https://api.slack.com/apps -> Create New App -> From scratch
  2. Pick your workspace, name it e.g. "Data Quality Bot"
  3. Left sidebar -> "Incoming Webhooks" -> toggle on
  4. "Add New Webhook to Workspace" -> choose a channel (e.g. #data-alerts)
  5. Copy the webhook URL (https://hooks.slack.com/services/...)
  6. Put it in your .env file as SLACK_WEBHOOK_URL=...  (see .env.example)

Without a webhook configured, send_alert() falls back to printing the
message to stdout ("dry run"), so the pipeline still works end-to-end.
"""
import requests

from src import config


def build_message(run_output: dict, table_name: str) -> str:
    failed = [r for r in run_output["results"] if not r.passed]
    lines = [
        f"*{table_name}* data quality run -- {run_output['run_date']}",
        f"Health score: *{run_output['health_score']}/100* ({run_output['status']})",
    ]
    if failed:
        lines.append("Failed checks:")
        for r in failed:
            label = r.check_name + (f" [{r.column_name}]" if r.column_name else "")
            lines.append(f"  - *{label}*: {r.message}")
    else:
        lines.append("All checks passed.")
    return "\n".join(lines)


def send_alert(run_output: dict, table_name: str = config.TABLE_NAME, webhook_url: str | None = None, dry_run: bool = False) -> bool:
    message = build_message(run_output, table_name)
    url = webhook_url or config.SLACK_WEBHOOK_URL

    if dry_run or not url:
        print("[Slack dry-run] Would send:\n" + message)
        return False

    response = requests.post(url, json={"text": message}, timeout=10)
    response.raise_for_status()
    return True
