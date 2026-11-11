CREATE TABLE IF NOT EXISTS upi_transactions (
    id BIGSERIAL PRIMARY KEY,
    transaction_id TEXT NOT NULL UNIQUE,
    event_ts TIMESTAMPTZ NOT NULL,
    bank TEXT NOT NULL CHECK (length(bank)>0),
    merchant_category TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    amount_inr NUMERIC(12,2) NOT NULL CHECK (amount_inr>0),
    status TEXT NOT NULL CHECK (status IN ('SUCCESS','FAILED','PENDING')),
    failure_reason TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((status = 'FAILED' AND failure_reason IS NOT NULL) OR
           (status <> 'FAILED' AND failure_reason IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_tx_event ON upi_transactions(event_ts);
CREATE INDEX IF NOT EXISTS idx_tx_bank_event ON upi_transactions(bank,event_ts);
CREATE INDEX IF NOT EXISTS idx_tx_status_event ON upi_transactions(status,event_ts);
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    input_rows INT NOT NULL DEFAULT 0,
    accepted_rows INT NOT NULL DEFAULT 0,
    duplicate_rows INT NOT NULL DEFAULT 0,
    rejected_rows INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    details TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('FAILURE_SPIKE','VOLUME_DROP')),
    bank TEXT NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('WARNING','CRITICAL')),
    metric NUMERIC(12,4) NOT NULL,
    baseline NUMERIC(12,4) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notification_status TEXT NOT NULL DEFAULT 'PENDING'
      CHECK (notification_status IN ('PENDING','SENT','FAILED')),
    notification_attempts INT NOT NULL DEFAULT 0,
    notified_at TIMESTAMPTZ,
    notification_error TEXT,
    UNIQUE(kind, bank, bucket_start)
);
CREATE INDEX IF NOT EXISTS idx_alert_notify ON alerts(notification_status, created_at);
CREATE OR REPLACE VIEW v_hourly_bank_kpis AS
SELECT date_trunc('hour',event_ts) AS hour_utc,
       bank,
       COUNT(*) AS total_transactions,
       COUNT(*) FILTER (WHERE status='SUCCESS') AS successful,
       COUNT(*) FILTER (WHERE status='FAILED') AS failed,
       COUNT(*) FILTER (WHERE status='PENDING') AS pending,
       ROUND(100.0*COUNT(*) FILTER (WHERE status='SUCCESS') /
         NULLIF(COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')),0),2) AS success_rate_pct,
       ROUND(100.0*COUNT(*) FILTER (WHERE status='FAILED') /
         NULLIF(COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')),0),2) AS failure_rate_pct,
       SUM(amount_inr) FILTER (WHERE status='SUCCESS') AS successful_value_inr,
       ROUND(AVG(amount_inr) FILTER (WHERE status='SUCCESS'),2) AS avg_successful_value_inr
FROM upi_transactions GROUP BY 1,2;
CREATE OR REPLACE VIEW v_daily_kpis AS
SELECT (event_ts AT TIME ZONE 'Asia/Kolkata')::date AS day_ist,
       COUNT(*) AS total_transactions,
       COUNT(*) FILTER (WHERE status='SUCCESS') AS successful,
       COUNT(*) FILTER (WHERE status='FAILED') AS failed,
       COUNT(*) FILTER (WHERE status='PENDING') AS pending,
       ROUND(100.0*COUNT(*) FILTER (WHERE status='SUCCESS') /
         NULLIF(COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')),0),2) AS success_rate_pct,
       ROUND(100.0*COUNT(*) FILTER (WHERE status='FAILED') /
         NULLIF(COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')),0),2) AS failure_rate_pct,
       COALESCE(SUM(amount_inr) FILTER (WHERE status='SUCCESS'),0) AS successful_value_inr
FROM upi_transactions GROUP BY 1;
CREATE OR REPLACE VIEW v_bank_kpis AS
SELECT bank, COUNT(*) AS total_transactions,
       COUNT(*) FILTER (WHERE status='SUCCESS') AS successful,
       COUNT(*) FILTER (WHERE status='FAILED') AS failed,
       COUNT(*) FILTER (WHERE status='PENDING') AS pending,
       ROUND(100.0*COUNT(*) FILTER (WHERE status='FAILED') /
         NULLIF(COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')),0),2) AS failure_rate_pct,
       COALESCE(SUM(amount_inr) FILTER (WHERE status='SUCCESS'),0) AS successful_value_inr
FROM upi_transactions GROUP BY 1;
CREATE OR REPLACE VIEW v_failure_reasons AS
SELECT bank, failure_reason, COUNT(*) AS failures
FROM upi_transactions WHERE status='FAILED' GROUP BY 1,2;

-- Additive migrations: existing alert history and notification status are preserved.
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS incident_status TEXT NOT NULL DEFAULT 'OPEN';
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS assignee TEXT;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS investigation_notes TEXT;
CREATE INDEX IF NOT EXISTS idx_alert_incident ON alerts(incident_status,created_at);
CREATE OR REPLACE VIEW v_incident_timeline AS
SELECT id,kind,bank,bucket_start,severity,metric,baseline,message,created_at,
       notification_status,incident_status,assignee,acknowledged_at,resolved_at,investigation_notes
FROM alerts;
CREATE OR REPLACE VIEW v_pipeline_quality AS
SELECT date_trunc('day',started_at) AS day_utc,
       COUNT(*) AS runs,
       SUM(input_rows) AS input_rows,
       SUM(accepted_rows) AS accepted_rows,
       SUM(duplicate_rows) AS duplicate_rows,
       SUM(rejected_rows) AS rejected_rows,
       ROUND(100.0*SUM(rejected_rows)/NULLIF(SUM(input_rows),0),2) AS rejection_pct
FROM ingestion_runs GROUP BY 1;
CREATE OR REPLACE VIEW v_failure_diagnostics AS
SELECT (event_ts AT TIME ZONE 'Asia/Kolkata')::date AS day_ist,
       EXTRACT(HOUR FROM event_ts AT TIME ZONE 'Asia/Kolkata')::int AS hour_ist,
       bank,merchant_category,failure_reason,
       COUNT(*) AS failed_payments,
       SUM(amount_inr) AS attempted_value_inr
FROM upi_transactions WHERE status='FAILED'
GROUP BY 1,2,3,4,5;
