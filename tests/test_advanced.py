"""Regression coverage for the advanced deterministic analytics model."""
import csv
from datetime import datetime, timezone
import pytest
from upi_analytics.config import Settings
from upi_analytics.simulator import make_hour, generate_history
from upi_analytics.detection import assess, HourMetrics
from upi_analytics.incidents import transition

HOUR = datetime(2026, 11, 11, 10, tzinfo=timezone.utc)


def test_market_basket_and_weekend_reproducible():
    saturday = datetime(2026, 11, 7, 18, tzinfo=timezone.utc)
    a = make_hour(saturday, "SBI", 36, 7)
    assert a == make_hour(saturday, "SBI", 36, 7)
    assert all(10 <= float(r["amount_inr"]) <= 75000 for r in a)
    assert len({r["transaction_id"] for r in a}) == len(a)


def test_ninety_days_supported(tmp_path):
    count = generate_history(tmp_path / "demo.csv", days=90, per_bank_hour=1, anchor=HOUR)
    assert count >= 90 * 24 * 4
    with (tmp_path / "demo.csv").open() as fh:
        assert sum(1 for _ in csv.DictReader(fh)) == count


def test_volume_median_robust_to_one_huge_day():
    history = [HourMetrics("SBI", 50, 50, 2) for _ in range(6)] + [HourMetrics("SBI", 10000, 10000, 3)]
    alerts = assess(HourMetrics("SBI", 20, 20, 1), history, Settings())
    assert [a.kind for a in alerts] == ["VOLUME_DROP"]
    assert alerts[0].baseline == 50.0


def test_incident_state_validation():
    with pytest.raises(ValueError):
        transition(None, 1, "SENT")
    with pytest.raises(ValueError):
        transition(None, 0, "OPEN")
