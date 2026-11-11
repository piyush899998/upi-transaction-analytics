"""Deterministic, reproducible synthetic payment event generation."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import random

BANKS = ("HDFC", "SBI", "ICICI", "AXIS")
CATEGORIES = ("GROCERY", "FOOD", "RETAIL", "TRAVEL", "UTILITIES", "FUEL")
REASONS = ("BANK_TIMEOUT", "NETWORK_ERROR", "INSUFFICIENT_FUNDS", "UPI_PIN_INVALID", "BANK_DECLINED")
COLUMNS = ("transaction_id", "event_ts", "bank", "merchant_category", "payment_method", "amount_inr", "status", "failure_reason")


def completed_hour(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


def _rng(seed: int, bucket: datetime, bank: str) -> random.Random:
    raw = f"{seed}|{bucket.isoformat()}|{bank}".encode("utf8")
    return random.Random(int.from_bytes(hashlib.sha256(raw).digest()[:8], "big"))


def make_hour(bucket: datetime, bank: str, base_count: int, seed: int, incident: str = "") -> list[dict]:
    if bucket.tzinfo is None:
        raise ValueError("bucket must be timezone-aware")
    if bank not in BANKS:
        raise ValueError("Unknown simulated bank")
    rng = _rng(seed, bucket, bank)
    hour = bucket.astimezone(timezone.utc).hour
    # Weekend and daily cycles affect volume; stable for the same seed, bank and hour.
    weekend = bucket.weekday() >= 5
    traffic_factor = 0.62 if hour < 5 else 1.30 if 12 <= hour <= 15 else 1.45 if 18 <= hour <= 22 else 1.0
    bank_factor = {"HDFC": 1.12, "SBI": 0.95, "ICICI": 1.06, "AXIS": 0.88}[bank]
    weekend_factor = 1.18 if weekend and 12 <= hour <= 22 else 0.91 if weekend else 1.0
    count = max(1, round(base_count * traffic_factor * bank_factor * weekend_factor * rng.uniform(0.90, 1.10)))
    if incident == "VOLUME_DROP":
        count = max(1, round(count * 0.2))
    failed_probability = 0.38 if incident == "FAILURE_SPIKE" else {"HDFC": 0.032, "SBI": 0.058, "ICICI": 0.041, "AXIS": 0.047}[bank]
    out: list[dict] = []
    for i in range(count):
        moment = bucket + timedelta(seconds=rng.randint(0, 3599))
        p = rng.random()
        status = "FAILED" if p < failed_probability else "PENDING" if p < failed_probability + 0.01 else "SUCCESS"
        reason = rng.choice(REASONS) if status == "FAILED" else ""
        txid = hashlib.sha256(f"{seed}|{bucket.isoformat()}|{bank}|{i}".encode()).hexdigest()[:24].upper()
        # Category-sensitive right-skewed basket sizes, capped at realistic demo ceilings.
        category = rng.choice(CATEGORIES)
        median_amount = {"GROCERY": 650, "FOOD": 310, "RETAIL": 1400, "TRAVEL": 2200,
                         "UTILITIES": 950, "FUEL": 850}[category]
        amount = round(min(75000, max(10, rng.lognormvariate(0, 0.75) * median_amount)), 2)
        out.append({"transaction_id": f"SIM-{txid}", "event_ts": moment.isoformat(), "bank": bank,
                    "merchant_category": category, "payment_method": "UPI",
                    "amount_inr": f"{amount:.2f}", "status": status, "failure_reason": reason})
    return out


def generate_history(path: Path, days: int = 8, per_bank_hour: int = 36, seed: int = 20261111,
                     anchor: datetime | None = None, incidents: bool = True) -> int:
    anchor = anchor or completed_hour()
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for offset in range((days * 24) - 1, -1, -1):
            hour = anchor - timedelta(hours=offset)
            for bank in BANKS:
                incident = "FAILURE_SPIKE" if incidents and offset == 0 and bank == "ICICI" else (
                    "VOLUME_DROP" if incidents and offset == 0 and bank == "SBI" else "")
                rows = make_hour(hour, bank, per_bank_hour, seed, incident)
                writer.writerows(rows)
                total += len(rows)
    return total


def generate_incremental(path: Path, anchor: datetime | None = None, per_bank_hour: int = 36,
                         seed: int = 20261111, incidents: bool = False) -> int:
    anchor = anchor or completed_hour()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        total = 0
        for bank in BANKS:
            incident = "FAILURE_SPIKE" if incidents and bank == "ICICI" else (
                "VOLUME_DROP" if incidents and bank == "SBI" else "")
            rows = make_hour(anchor, bank, per_bank_hour, seed, incident)
            writer.writerows(rows)
            total += len(rows)
    return total
