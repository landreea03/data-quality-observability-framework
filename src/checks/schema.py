from src.checks.base import CheckResult


def check_schema(today_columns: set, expected_columns: set) -> list:
    """Flags dropped columns (upstream rename/removal) and unexpected new ones."""
    results = []
    missing = expected_columns - today_columns
    extra = today_columns - expected_columns

    if missing:
        results.append(CheckResult(
            check_name="schema",
            passed=False,
            severity="high",
            message=f"Missing expected column(s): {', '.join(sorted(missing))}.",
        ))
    if extra:
        results.append(CheckResult(
            check_name="schema",
            passed=False,
            severity="medium",
            message=f"Unexpected new column(s): {', '.join(sorted(extra))}.",
        ))
    if not missing and not extra:
        results.append(CheckResult(
            check_name="schema",
            passed=True,
            severity="low",
            message="Schema unchanged.",
        ))
    return results
