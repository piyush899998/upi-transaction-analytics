# Data dictionary & KPI definitions

All records are synthetic and represent attempted UPI-style payments. Bank names are simulated segments for practice, not actual bank incident evidence.

| Column | Type | Meaning |
|---|---|---|
| `transaction_id` | text unique | Deterministic synthetic id; protects against double counting on import replay |
| `event_ts` | timestamptz | Event time, stored with timezone and normalized by PostgreSQL |
| `bank` | text | Simulated issuing-bank label |
| `merchant_category` | text | Synthetic merchant category |
| `payment_method` | text | `UPI` in this project's generator |
| `amount_inr` | numeric(12,2) | Attempted amount, INR |
| `status` | text | `SUCCESS`, `FAILED`, `PENDING` |
| `failure_reason` | text/null | Required only for failed attempts |
| `ingested_at` | timestamptz | Database ingestion timestamp |

## KPI formulas

- Attempted transaction volume = COUNT(*), including pending attempts.
- Resolved count = successful + failed, excludes pending.
- Success rate = successful / resolved × 100.
- Failure rate = failed / resolved × 100.
- Pending count = COUNT(status='PENDING').
- Successful monetary value (INR) = SUM(amount_inr for success transactions only).
- Average successful ticket = successful monetary value / successful count.
- Day for daily KPI view is India Standard Time; anomaly monitoring uses UTC hourly buckets consistently for history/current.

## Simulated anomalies

On the most recently completed UTC hour in generated demo history:
- ICICI: failure probability rises to ~38% vs normal ~4.5%.
- SBI: volume shrinks to ~20% of the comparable typical hour.

A fixed seed makes the data reproducible at a given UTC hour. The exact record counts vary with that hour's normal daily traffic factor.

## Data quality checks

- Reject empty ID, bank or merchant category, unsupported status and method.
- Require timezone-aware ISO timestamps.
- Reject NaN, infinities, zero/negative amounts, amounts exceeding SQL column capacity or >2 decimal places.
- Require a failure reason on failed transactions and prohibit one on nonfailed transactions.
- Deduplicate exact transaction IDs using a unique index and PostgreSQL `ON CONFLICT DO NOTHING`.
- Record imported, duplicate and rejected row counts in `ingestion_runs`.

## Advanced analytics additions

`alerts.incident_status` = OPEN / INVESTIGATING / RESOLVED; `alerts.assignee`, `acknowledged_at`, `resolved_at`, `investigation_notes` are optional manual incident metadata. `v_incident_timeline` exposes incident state; `v_pipeline_quality` summarizes per-day import outcomes; `v_failure_diagnostics` groups failed payments by local date/hour, bank, merchant category and failure reason. Power BI CSV exports contain synthetic demo data only.
