from src.checks.base import CheckResult


def check_freshness(today_df, expected_min_rows: int = 1) -> CheckResult:
    """Did any data actually arrive for this run at all?"""
    row_count = len(today_df)
    passed = row_count >= expected_min_rows
    return CheckResult(
        check_name="freshness",
        passed=passed,
        severity="low" if passed else "high",
        message=("No new data arrived (0 rows)." if row_count == 0 else f"Data arrived: {row_count} rows."),
        metric_value=float(row_count),
    )
