"""Transparent same-hour historical baselines and deterministic alert rules."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from psycopg import Connection
from .config import Settings

@dataclass(frozen=True)
class HourMetrics:
    bank: str
    total: int
    resolved: int
    failed: int

    @property
    def failure_rate(self) -> float:
        return self.failed / self.resolved if self.resolved else 0.0


@dataclass(frozen=True)
class Anomaly:
    kind: str
    bank: str
    severity: str
    metric: float
    baseline: float
    message: str


def assess(current: HourMetrics, history: list[HourMetrics], cfg: Settings) -> list[Anomaly]:
    """Compare to the same clock hour on up to seven prior days (minimum three)."""
    if len(history) < 3:
        return []
    result = []
    # Weight historical failure rates by resolved counts to avoid unstable small-hour ratios.
    historic_resolved = sum(p.resolved for p in history)
    historic_failed = sum(p.failed for p in history)
    baseline_rate = historic_failed / historic_resolved if historic_resolved else 0.0
    current_rate = current.failure_rate
    if (current.resolved >= cfg.failure_min_txns
            and current_rate >= cfg.failure_threshold
            and current_rate >= baseline_rate * cfg.failure_multiplier
            and current_rate - baseline_rate >= cfg.failure_min_abs_increase):
        severity = "CRITICAL" if current_rate >= 0.30 else "WARNING"
        result.append(Anomaly("FAILURE_SPIKE", current.bank, severity, round(current_rate, 4),
            round(baseline_rate, 4), f"{current.bank}: failure rate {current_rate:.1%} vs {baseline_rate:.1%} baseline ({current.failed}/{current.resolved} resolved payments)."))
    # Robust against one-off traffic outliers on otherwise comparable days.
    baseline_volume = median(p.total for p in history)
    if (baseline_volume >= cfg.volume_min_baseline and
            current.total < baseline_volume * cfg.volume_drop_ratio):
        severity = "CRITICAL" if current.total < baseline_volume * 0.3 else "WARNING"
        result.append(Anomaly("VOLUME_DROP", current.bank, severity, float(current.total),
            round(baseline_volume, 4), f"{current.bank}: only {current.total} transactions vs {baseline_volume:.1f} normal for this UTC hour."))
    return result


def _metrics_for_hour(conn: "Connection", hour: datetime) -> dict[str, HourMetrics]:
    rows = conn.execute("""SELECT bank, COUNT(*)::integer AS total,
        COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED'))::integer AS resolved,
        COUNT(*) FILTER (WHERE status='FAILED')::integer AS failed
        FROM upi_transactions WHERE event_ts >= %s AND event_ts < %s GROUP BY bank""",
        (hour, hour + timedelta(hours=1))).fetchall()
    return {bank: HourMetrics(bank, total, resolved, failed) for bank, total, resolved, failed in rows}


def detect_hour(conn: "Connection", cfg: Settings, bucket: datetime) -> list[Anomaly]:
    if bucket.tzinfo is None:
        raise ValueError("hour must be timezone-aware")
    bucket = bucket.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    current = _metrics_for_hour(conn, bucket)
    if not current:
        return []
    historical = [_metrics_for_hour(conn, bucket - timedelta(days=i)) for i in range(1, 8)]
    anomalies: list[Anomaly] = []
    for bank, metric in current.items():
        history = [h[bank] for h in historical if bank in h]
        anomalies.extend(assess(metric, history, cfg))
    with conn.transaction():
        for a in anomalies:
            conn.execute("""INSERT INTO alerts(kind,bank,bucket_start,severity,metric,baseline,message)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (kind,bank,bucket_start) DO NOTHING""",
                (a.kind, a.bank, bucket, a.severity, a.metric, a.baseline, a.message))
    return anomalies
