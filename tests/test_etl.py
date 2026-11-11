import pytest
from upi_analytics.etl import validate

ROW = {"transaction_id": "TX-1", "event_ts": "2026-11-11T10:00:00+00:00", "bank": "SBI",
       "merchant_category": "FOOD", "payment_method": "UPI", "amount_inr": "100.00",
       "status": "FAILED", "failure_reason": "BANK_TIMEOUT"}


def test_valid():
    row = validate(ROW)
    assert row[0] == "TX-1" and row[6] == "FAILED" and row[7] == "BANK_TIMEOUT"

@pytest.mark.parametrize("changes", [
    {"transaction_id": ""}, {"status": "REVERSED"}, {"amount_inr": "-1"},
    {"amount_inr": "NaN"}, {"amount_inr": "10.123"}, {"event_ts": "2026-11-11T10:00:00"},
    {"status": "SUCCESS"}, {"failure_reason": ""}, {"payment_method": "CARD"},
])
def test_invalid(changes):
    with pytest.raises(ValueError):
        validate({**ROW, **changes})
