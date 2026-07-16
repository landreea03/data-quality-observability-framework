from src import config
from src.checks.base import CheckResult


def check_nulls(today_df, column: str, historical_null_rates: list) -> CheckResult:
    """Flags a null-rate spike relative to each column's own rolling baseline
    (a column that's normally 0.3% null triggering at 40% null is what this catches)."""
    total = len(today_df)
    if total == 0 or column not in today_df.columns:
        return CheckResult(
            check_name="nulls",
            column_name=column,
            passed=True,
            severity="low",
            message=f"Column '{column}' not present or no rows to check.",
        )

    today_rate = float(today_df[column].isna().mean())

    if len(historical_null_rates) < config.MIN_HISTORY_DAYS:
        return CheckResult(
            check_name="nulls",
            column_name=column,
            passed=True,
            severity="low",
            message=f"'{column}' null rate {today_rate * 100:.1f}% (baseline still building).",
            metric_value=today_rate,
        )

    baseline_rate = sum(historical_null_rates) / len(historical_null_rates)
    threshold = max(baseline_rate * config.NULL_RATE_SPIKE_MULTIPLIER, config.NULL_RATE_FLOOR)
    passed = today_rate <= threshold

    return CheckResult(
        check_name="nulls",
        column_name=column,
        passed=passed,
        severity="low" if passed else "high",
        message=(
            f"'{column}' null rate normal: {today_rate * 100:.1f}% (baseline {baseline_rate * 100:.1f}%)."
            if passed
            else f"'{column}' null rate spiked: {today_rate * 100:.1f}% (baseline {baseline_rate * 100:.1f}%)."
        ),
        metric_value=today_rate,
        baseline_mean=baseline_rate,
    )
