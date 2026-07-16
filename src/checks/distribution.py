import statistics

from src import config
from src.checks.base import CheckResult


def check_distribution(today_df, column: str, historical_means: list) -> CheckResult:
    """Flags a shift in a numeric column's average vs. its rolling baseline
    (e.g. a currency/unit bug that pushes 'price' from ~$87 to ~$91k)."""
    if column not in today_df.columns or today_df[column].dropna().empty:
        return CheckResult(
            check_name="distribution",
            column_name=column,
            passed=True,
            severity="low",
            message=f"'{column}' not present or empty; skipped.",
        )

    today_mean = float(today_df[column].dropna().mean())

    if len(historical_means) < config.MIN_HISTORY_DAYS:
        return CheckResult(
            check_name="distribution",
            column_name=column,
            passed=True,
            severity="low",
            message=f"'{column}' mean {today_mean:.2f} (baseline still building).",
            metric_value=today_mean,
        )

    baseline_mean = statistics.mean(historical_means)
    baseline_std = statistics.pstdev(historical_means) or 1.0
    z = (today_mean - baseline_mean) / baseline_std
    passed = abs(z) <= config.Z_SCORE_THRESHOLD

    return CheckResult(
        check_name="distribution",
        column_name=column,
        passed=passed,
        severity="low" if passed else "high",
        message=(
            f"'{column}' mean normal: {today_mean:.2f} (baseline {baseline_mean:.2f} +/- {baseline_std:.2f})."
            if passed
            else f"'{column}' mean shifted: {today_mean:.2f} vs baseline {baseline_mean:.2f} +/- {baseline_std:.2f} (z={z:.2f})."
        ),
        metric_value=today_mean,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
    )
