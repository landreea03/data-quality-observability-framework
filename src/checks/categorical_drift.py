"""
Population Stability Index (PSI) -- the standard technique risk and ML
teams use in production to detect when a categorical column's distribution
has shifted shape, not just its mean. Catches things z-scores on numeric
columns can't: e.g. the 'status' column suddenly having way more
'refunded' orders than usual, even though row count and price look fine.

    PSI = sum over categories of (today% - baseline%) * ln(today% / baseline%)

Industry rule of thumb for interpreting the score:
    PSI < 0.10             -> no significant shift
    0.10 <= PSI < 0.25     -> moderate shift, worth a look
    PSI >= 0.25            -> significant shift, likely a real problem
"""
import math

from src.checks.base import CheckResult

PSI_MODERATE_THRESHOLD = 0.10
PSI_SIGNIFICANT_THRESHOLD = 0.25
EPSILON = 1e-4  # floor so a 0% category doesn't blow up log(0) / divide-by-zero


def _proportions(series, categories) -> dict:
    total = len(series)
    if total == 0:
        return {c: 0.0 for c in categories}
    counts = series.value_counts()
    return {c: counts.get(c, 0) / total for c in categories}


def compute_psi(today_props: dict, baseline_props: dict) -> float:
    categories = set(today_props) | set(baseline_props)
    psi = 0.0
    for c in categories:
        a = max(today_props.get(c, 0.0), EPSILON)
        b = max(baseline_props.get(c, 0.0), EPSILON)
        psi += (a - b) * math.log(a / b)
    return float(psi)  # guard against numpy.float64 leaking out (breaks psycopg2 inserts)


def check_categorical_drift(today_df, column: str, historical_df) -> CheckResult:
    if column not in today_df.columns or today_df[column].dropna().empty:
        return CheckResult(
            check_name="categorical_drift",
            column_name=column,
            passed=True,
            severity="low",
            message=f"'{column}' not present or empty; skipped.",
        )

    if historical_df.empty or column not in historical_df.columns:
        return CheckResult(
            check_name="categorical_drift",
            column_name=column,
            passed=True,
            severity="low",
            message=f"'{column}' distribution baseline still building.",
        )

    categories = set(today_df[column].dropna().unique()) | set(historical_df[column].dropna().unique())
    today_props = _proportions(today_df[column].dropna(), categories)
    baseline_props = _proportions(historical_df[column].dropna(), categories)

    psi = compute_psi(today_props, baseline_props)

    if psi >= PSI_SIGNIFICANT_THRESHOLD:
        passed, severity = False, "high"
    elif psi >= PSI_MODERATE_THRESHOLD:
        passed, severity = False, "medium"
    else:
        passed, severity = True, "low"

    # Name the single category that moved the most, for a human-readable message.
    biggest = max(categories, key=lambda c: abs(today_props.get(c, 0) - baseline_props.get(c, 0)))
    delta = today_props.get(biggest, 0) - baseline_props.get(biggest, 0)
    sign = "+" if delta >= 0 else ""

    return CheckResult(
        check_name="categorical_drift",
        column_name=column,
        passed=passed,
        severity=severity,
        message=(
            f"'{column}' distribution stable (PSI={psi:.3f})."
            if passed
            else (
                f"'{column}' distribution shifted (PSI={psi:.3f}); "
                f"'{biggest}' went from {baseline_props.get(biggest, 0) * 100:.1f}% to "
                f"{today_props.get(biggest, 0) * 100:.1f}% ({sign}{delta * 100:.1f}pp)."
            )
        ),
        metric_value=psi,
    )
