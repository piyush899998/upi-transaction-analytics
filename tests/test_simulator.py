from datetime import datetime, timezone, timedelta
import csv
from upi_analytics.simulator import make_hour, completed_hour, generate_history, BANKS

HOUR = datetime(2026, 11, 11, 10, tzinfo=timezone.utc)


def test_deterministic():
    assert make_hour(HOUR, "ICICI", 36, 42) == make_hour(HOUR, "ICICI", 36, 42)


def test_incidents_are_real():
    baseline = make_hour(HOUR, "SBI", 60, 42)
    dropped = make_hour(HOUR, "SBI", 60, 42, "VOLUME_DROP")
    assert len(dropped) < len(baseline) / 2
    failure = make_hour(HOUR, "ICICI", 500, 42, "FAILURE_SPIKE")
    assert sum(r["status"] == "FAILED" for r in failure) / len(failure) > 0.25


def test_completed_hour_utc():
    assert completed_hour(HOUR + timedelta(minutes=28)) == HOUR - timedelta(hours=1)


def test_history_has_unique_ids(tmp_path):
    target = tmp_path / "history.csv"
    count = generate_history(target, days=2, per_bank_hour=10, anchor=HOUR)
    with target.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == count
    assert len({r["transaction_id"] for r in rows}) == count
    assert set(r["bank"] for r in rows) == set(BANKS)
