from src.checks.base import CheckResult


def check_duplicates(today_df, key_columns: list) -> CheckResult:
    """Flags an unexpected spike in duplicate rows on the table's natural key."""
    if today_df.empty:
        return CheckResult(check_name="duplicates", passed=True, severity="low", message="No rows to check.")

    present_keys = [c for c in key_columns if c in today_df.columns]
    if not present_keys:
        return CheckResult(check_name="duplicates", passed=True, severity="low", message="Key columns unavailable; skipped.")

    dup_count = int(today_df.duplicated(subset=present_keys, keep=False).sum())
    dup_rate = dup_count / len(today_df)
    passed = dup_rate <= 0.01  # order_id duplicates should be ~0 in a healthy pipeline

    return CheckResult(
        check_name="duplicates",
        passed=passed,
        severity="low" if passed else "medium",
        message=(
            f"Duplicate rate normal: {dup_rate * 100:.2f}%."
            if passed
            else f"Duplicate rate spiked: {dup_rate * 100:.2f}% ({dup_count} rows) on key {present_keys}."
        ),
        metric_value=dup_rate,
    )
