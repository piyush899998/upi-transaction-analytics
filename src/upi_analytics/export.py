"""Power BI Service-ready CSV exports built from PostgreSQL reporting views."""
import csv
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from psycopg import Connection

EXPORTS = {
    "transactions": "SELECT transaction_id,event_ts,bank,merchant_category,payment_method,amount_inr,status,failure_reason FROM upi_transactions ORDER BY event_ts",
    "hourly_bank": "SELECT * FROM v_hourly_bank_kpis ORDER BY hour_utc,bank",
    "daily": "SELECT * FROM v_daily_kpis ORDER BY day_ist",
    "failure_diagnostics": "SELECT * FROM v_failure_diagnostics ORDER BY day_ist,hour_ist",
    "incidents": "SELECT * FROM v_incident_timeline ORDER BY created_at",
    "data_quality": "SELECT * FROM v_pipeline_quality ORDER BY day_utc",
}


def export_views(conn: "Connection", output: Path) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    totals = {}
    for name, statement in EXPORTS.items():
        with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            with conn.cursor() as cur:
                cur.execute(statement)
                writer = csv.writer(fh)
                writer.writerow([col.name for col in cur.description])
                count = 0
                for row in cur:
                    writer.writerow([v.isoformat() if hasattr(v, "isoformat") else v for v in row])
                    count += 1
            totals[name] = count
    return totals
