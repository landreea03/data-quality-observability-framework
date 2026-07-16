from dataclasses import dataclass
from typing import Optional


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    severity: str  # "low", "medium", "high"
    message: str
    column_name: Optional[str] = None
    metric_value: Optional[float] = None
    baseline_mean: Optional[float] = None
    baseline_std: Optional[float] = None

    def to_dict(self):
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "column_name": self.column_name,
            "metric_value": self.metric_value,
            "baseline_mean": self.baseline_mean,
            "baseline_std": self.baseline_std,
        }
