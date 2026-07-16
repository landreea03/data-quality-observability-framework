import pandas as pd

from src.checks.categorical_drift import check_categorical_drift, compute_psi
from src.checks.distribution import check_distribution
from src.checks.duplicates import check_duplicates
from src.checks.nulls import check_nulls
from src.checks.schema import check_schema
from src.checks.volume import check_volume


def test_null_spike_detected():
    today = pd.DataFrame({"customer_id": [None] * 40 + ["C-1"] * 60})
    baseline = [0.003] * 10
    result = check_nulls(today, "customer_id", baseline)
    assert result.passed is False
    assert result.severity == "high"


def test_null_rate_within_baseline_passes():
    today = pd.DataFrame({"customer_id": [None] * 1 + ["C-1"] * 99})
    baseline = [0.01] * 10
    result = check_nulls(today, "customer_id", baseline)
    assert result.passed is True


def test_volume_drop_detected():
    result = check_volume(250, [5000] * 14)
    assert result.passed is False


def test_volume_normal_passes():
    counts = [5000, 4800, 5200, 4900, 5100, 5050, 4950, 5000, 5150, 4850, 5050, 4950, 5100, 5000]
    result = check_volume(5080, counts)
    assert result.passed is True


def test_distribution_shift_detected():
    today = pd.DataFrame({"price": [50000.0] * 10 + [87.0] * 90})
    baseline_means = [87.0] * 14
    result = check_distribution(today, "price", baseline_means)
    assert result.passed is False


def test_distribution_stable_passes():
    today = pd.DataFrame({"price": [86.0, 88.0, 87.0, 90.0]})
    baseline_means = [87.0] * 14
    result = check_distribution(today, "price", baseline_means)
    assert result.passed is True


def test_schema_missing_column_detected():
    results = check_schema({"order_id", "price"}, {"order_id", "price", "customer_id"})
    assert any(not r.passed for r in results)


def test_schema_unchanged_passes():
    cols = {"order_id", "price", "customer_id"}
    results = check_schema(cols, cols)
    assert all(r.passed for r in results)


def test_duplicates_detected():
    df = pd.DataFrame({"order_id": [1, 1, 1, 2, 3, 4, 5, 6, 7, 8]})
    result = check_duplicates(df, ["order_id"])
    assert result.passed is False


def test_duplicates_normal_passes():
    df = pd.DataFrame({"order_id": list(range(100))})
    result = check_duplicates(df, ["order_id"])
    assert result.passed is True


def test_psi_zero_when_identical():
    props = {"completed": 0.9, "cancelled": 0.05, "refunded": 0.05}
    assert compute_psi(props, props) == 0.0


def test_psi_flags_refund_spike():
    baseline = {"completed": 0.90, "cancelled": 0.05, "refunded": 0.05}
    today = {"completed": 0.60, "cancelled": 0.05, "refunded": 0.35}
    psi = compute_psi(today, baseline)
    assert psi >= 0.25  # "significant shift" per the standard PSI rule of thumb


def test_categorical_drift_detects_refund_spike():
    baseline_rows = (["completed"] * 900 + ["cancelled"] * 50 + ["refunded"] * 50) * 3
    historical_df = pd.DataFrame({
        "status": baseline_rows,
        "load_date": (["2026-06-01"] * 1000 + ["2026-06-02"] * 1000 + ["2026-06-03"] * 1000),
    })
    today_df = pd.DataFrame({
        "status": ["completed"] * 600 + ["cancelled"] * 50 + ["refunded"] * 350,
    })
    result = check_categorical_drift(today_df, "status", historical_df)
    assert result.passed is False
    assert result.severity == "high"


def test_categorical_drift_stable_passes():
    baseline_rows = (["completed"] * 900 + ["cancelled"] * 50 + ["refunded"] * 50) * 3
    historical_df = pd.DataFrame({
        "status": baseline_rows,
        "load_date": (["2026-06-01"] * 1000 + ["2026-06-02"] * 1000 + ["2026-06-03"] * 1000),
    })
    today_df = pd.DataFrame({"status": ["completed"] * 890 + ["cancelled"] * 55 + ["refunded"] * 55})
    result = check_categorical_drift(today_df, "status", historical_df)
    assert result.passed is True
