"""Validated, idempotent batch import with accurate counters and audit trail."""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from psycopg import Connection

REQUIRED = {"transaction_id", "event_ts", "bank", "merchant_category", "payment_method", "amount_inr", "status", "failure_reason"}

def validate(row: dict) -> tuple:
    txid = (row.get("transaction_id") or "").strip()
    bank = (row.get("bank") or "").strip().upper()
    category = (row.get("merchant_category") or "").strip().upper()
    method = (row.get("payment_method") or "").strip().upper()
    status = (row.get("status") or "").strip().upper()
    reason = (row.get("failure_reason") or "").strip().upper() or None
    if not txid or not bank or not category or method != "UPI" or status not in ("SUCCESS", "FAILED", "PENDING"):
        raise ValueError("Missing or invalid identifiers, category, method, or status")
    try:
        ts = datetime.fromisoformat((row.get("event_ts") or "").strip().replace("Z", "+00:00"))
        amount = Decimal((row.get("amount_inr") or "").strip())
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid timestamp or amount") from exc
    if ts.tzinfo is None or not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
        raise ValueError("Timestamp must have a time zone, and amount must be positive and finite")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Amount may have at most 2 decimal places")
    if (status == "FAILED") != (reason is not None):
        raise ValueError("Failed transactions require a reason; others must not have one")
    return (txid, ts, bank, category, method, amount, status, reason)


def _insert_batch(conn: "Connection", items: list[tuple]) -> int:
    """One parameterized INSERT per chunk, orders of magnitude fewer DB roundtrips."""
    if not items:
        return 0
    columns = 8
    row_expr = "(" + ",".join(["%s"] * columns) + ")"
    statement = """INSERT INTO upi_transactions(transaction_id,event_ts,bank,merchant_category,
        payment_method,amount_inr,status,failure_reason) VALUES """ + ",".join(
            [row_expr] * len(items)) + " ON CONFLICT (transaction_id) DO NOTHING"
    flattened = [v for item in items for v in item]
    return conn.execute(statement, flattened).rowcount


def ingest_csv(conn: "Connection", source: Path) -> dict:
    if not source.is_file():
        raise FileNotFoundError(source)
    stats = {"input_rows": 0, "accepted_rows": 0, "duplicate_rows": 0, "rejected_rows": 0}
    with source.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV missing required columns: {sorted(REQUIRED - set(reader.fieldnames or []))}")
        with conn.transaction():
            run_id = conn.execute("INSERT INTO ingestion_runs(source) VALUES (%s) RETURNING id", (str(source),)).fetchone()[0]
            chunk = []

            def flush() -> None:
                if not chunk:
                    return
                try:
                    with conn.transaction():
                        inserted = _insert_batch(conn, chunk)
                    stats["accepted_rows"] += inserted
                    stats["duplicate_rows"] += len(chunk) - inserted
                except Exception:
                    # Unexpected DB errors (e.g. constraint failures) are isolated to rows.
                    for values in chunk:
                        try:
                            with conn.transaction():
                                inserted = _insert_batch(conn, [values])
                            stats["accepted_rows" if inserted else "duplicate_rows"] += 1
                        except Exception:
                            stats["rejected_rows"] += 1
                chunk.clear()

            for row in reader:
                stats["input_rows"] += 1
                try:
                    chunk.append(validate(row))
                except ValueError:
                    stats["rejected_rows"] += 1
                    continue
                if len(chunk) >= 300:
                    flush()
            flush()
            conn.execute("""UPDATE ingestion_runs SET finished_at=now(), input_rows=%s, accepted_rows=%s,
                        duplicate_rows=%s,rejected_rows=%s,status='COMPLETED' WHERE id=%s""",
                        (*stats.values(), run_id))
    stats["run_id"] = run_id
    return stats
