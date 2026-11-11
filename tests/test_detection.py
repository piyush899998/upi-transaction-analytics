from upi_analytics.config import Settings
from upi_analytics.detection import assess, HourMetrics

CFG = Settings()


def historical(bank="ICICI", volume=40):
    return [HourMetrics(bank, volume, volume, 2) for _ in range(7)]


def test_spike():
    found = assess(HourMetrics("ICICI", 40, 40, 17), historical(), CFG)
    assert [a.kind for a in found] == ["FAILURE_SPIKE"]
    assert found[0].severity == "CRITICAL"


def test_volume_drop():
    found = assess(HourMetrics("SBI", 5, 5, 0), historical("SBI"), CFG)
    assert [a.kind for a in found] == ["VOLUME_DROP"]


def test_no_alert_for_normal():
    assert assess(HourMetrics("ICICI", 40, 40, 2), historical(), CFG) == []


def test_minimum_history():
    assert assess(HourMetrics("ICICI", 40, 40, 30), historical()[:2], CFG) == []


def test_no_spike_with_few_resolved():
    assert not any(a.kind == "FAILURE_SPIKE" for a in assess(HourMetrics("ICICI", 5, 5, 5), historical(), CFG))


def test_pending_is_excluded_from_rate():
    metrics = HourMetrics("ICICI", 25, 20, 4)
    assert metrics.failure_rate == 0.2
