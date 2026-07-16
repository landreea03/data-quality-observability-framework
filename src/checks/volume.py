import statistics

from src import config
from src.checks.base import CheckResult


def check_volume(today_count: int, historical_counts: list) -> CheckResult:
    """Flags a row-count spike or drop using a rolling mean/std z-score,
    instead of a hardcoded 'if rows < 1000' threshold."""
    if len(historical_counts) < config.MIN_HISTORY_DAYS:
        return CheckResult(
            check_name="volume",
            passed=True,
            severity="low",
            message=f"Row count {today_count} (baseline still building: {len(historical_counts)}/{config.MIN_HISTORY_DAYS} days).",
            metric_value=float(today_count),
        )

    mean = statistics.mean(historical_counts)
    std = statistics.pstdev(historical_counts) or 1.0
    z = (today_count - mean) / std
    passed = abs(z) <= config.Z_SCORE_THRESHOLD
    direction = "dropped" if z < 0 else "spiked"

    return CheckResult(
        check_name="volume",
        passed=passed,
        severity="low" if passed else "high",
        message=(
            f"Row count normal: {today_count} (baseline {mean:.0f} +/- {std:.0f})."
            if passed
            else f"Row count {direction}: {today_count} vs baseline {mean:.0f} +/- {std:.0f} (z={z:.2f})."
        ),
        metric_value=float(today_count),
        baseline_mean=mean,
        baseline_std=std,
    )
