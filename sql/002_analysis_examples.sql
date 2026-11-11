-- Useful interview-ready SQL analytics examples.
-- 1) Rolling 7-day average daily transaction volume (Indian calendar days).
SELECT day_ist, total_transactions,
  ROUND(AVG(total_transactions) OVER (ORDER BY day_ist ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),2) AS rolling_7d_volume
FROM v_daily_kpis ORDER BY day_ist;

-- 2) Day-over-day count change (only adjacent calendar-day rows present).
SELECT day_ist, total_transactions,
  LAG(total_transactions) OVER (ORDER BY day_ist) AS previous_day_transactions,
  total_transactions - LAG(total_transactions) OVER (ORDER BY day_ist) AS absolute_change
FROM v_daily_kpis ORDER BY day_ist;

-- 3) Bank-level failure percentages (resolved payments only; pending excluded).
SELECT bank,total_transactions,failed,successful,pending,failure_rate_pct
FROM v_bank_kpis ORDER BY failure_rate_pct DESC NULLS LAST;

-- 4) Error clusters to inspect.
SELECT bank, failure_reason, failures,
  RANK() OVER (PARTITION BY bank ORDER BY failures DESC) AS reason_rank
FROM v_failure_reasons ORDER BY bank,reason_rank;

-- 5) Latest detected incidents.
SELECT bucket_start,bank,kind,severity,metric,baseline,notification_status,message
FROM alerts ORDER BY bucket_start DESC,bank LIMIT 100;

-- 6) Import quality and duplicate replay rates.
SELECT started_at,source,input_rows,accepted_rows,duplicate_rows,rejected_rows,
       ROUND(100.0*rejected_rows/NULLIF(input_rows,0),2) AS reject_pct
FROM ingestion_runs ORDER BY started_at DESC LIMIT 20;
