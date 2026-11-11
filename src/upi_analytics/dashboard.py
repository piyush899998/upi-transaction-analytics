"""Fully runnable dashboard for local or Docker deployment; Power BI assets also included."""
import os
import pandas as pd
import plotly.express as px
import streamlit as st
import psycopg
from psycopg.rows import dict_row

st.set_page_config(page_title="UPI Payment Intelligence", page_icon="📊", layout="wide")
st.title("UPI Payment Intelligence")
st.caption("Synthetic transactions only · All transaction times stored in UTC · Daily summaries use IST")

@st.cache_data(ttl=60)
def query(sql: str, args: tuple = ()) -> pd.DataFrame:
    url = os.getenv("DATABASE_URL", "postgresql://upi:upi_local_dev@localhost:5432/upi_analytics")
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=5) as conn:
        return pd.DataFrame(conn.execute(sql, args).fetchall())

try:
    banks = query("SELECT DISTINCT bank FROM upi_transactions ORDER BY bank")
except (psycopg.Error, OSError):
    st.error("Cannot connect to PostgreSQL or schema not initialized. Follow README setup instructions.")
    st.stop()
if banks.empty:
    st.info("No transactions yet. Run `python -m upi_analytics.cli demo` or start the worker.")
    st.stop()

selected = st.sidebar.multiselect("Banks", banks.bank.tolist(), default=banks.bank.tolist())
days = st.sidebar.slider("Lookback days", 1, 90, 30)
if not selected:
    st.warning("Select at least one bank")
    st.stop()

# Bank selection uses PostgreSQL's ANY with bound parameters, never concatenated values.
from datetime import datetime, timedelta, timezone
since = datetime.now(timezone.utc) - timedelta(days=days)
where = "WHERE event_ts >= %s AND bank = ANY(%s)"
params = (since, selected)
summary = query(f"""SELECT COUNT(*) AS total,
  COUNT(*) FILTER (WHERE status='SUCCESS') AS successes,
  COUNT(*) FILTER (WHERE status='FAILED') AS failures,
  COUNT(*) FILTER (WHERE status='PENDING') AS pending,
  COALESCE(SUM(amount_inr) FILTER (WHERE status='SUCCESS'),0) AS value_inr
  FROM upi_transactions {where}""", params).iloc[0]
resolved = int(summary.successes + summary.failures)
success_rate = summary.successes / resolved * 100 if resolved else 0
cols = st.columns(5)
for col, label, val in zip(cols,
    ["Total transactions", "Success rate (resolved)", "Failures", "Pending", "Successful value"],
    [f"{int(summary.total):,}", f"{success_rate:.2f}%", f"{int(summary.failures):,}",
     f"{int(summary.pending):,}", f"₹{float(summary.value_inr):,.0f}"]):
    col.metric(label, val)

hourly = query(f"""SELECT date_trunc('hour',event_ts) AS hour_utc, bank,
    COUNT(*)::int AS transactions,
    COUNT(*) FILTER (WHERE status='FAILED')::int AS failures,
    COUNT(*) FILTER (WHERE status IN ('FAILED','SUCCESS'))::int AS resolved
    FROM upi_transactions {where} GROUP BY 1,2 ORDER BY 1,2""", params)
if not hourly.empty:
    hourly["failure_rate_pct"] = (hourly.failures / hourly.resolved.replace(0, float("nan")) * 100).fillna(0)
    left, right = st.columns(2)
    left.plotly_chart(px.line(hourly, x="hour_utc", y="transactions", color="bank",
                              title="Hourly transaction volume (UTC)"), use_container_width=True)
    right.plotly_chart(px.line(hourly, x="hour_utc", y="failure_rate_pct", color="bank",
                               title="Failure rate by bank (%)"), use_container_width=True)

bank_summary = query(f"""SELECT bank,COUNT(*)::int AS transactions,
    COUNT(*) FILTER (WHERE status='FAILED')::int AS failures,
    COUNT(*) FILTER (WHERE status='SUCCESS')::int AS successes
    FROM upi_transactions {where} GROUP BY bank ORDER BY bank""", params)
reason_summary = query(f"""SELECT bank,failure_reason,COUNT(*)::int AS failures
    FROM upi_transactions {where} AND status='FAILED' GROUP BY 1,2 ORDER BY failures DESC""", params)
left, right = st.columns(2)
left.plotly_chart(px.bar(bank_summary, x="bank", y=["successes", "failures"], barmode="stack",
                         title="Resolved transactions by bank"), use_container_width=True)
if not reason_summary.empty:
    right.plotly_chart(px.bar(reason_summary, x="failure_reason", y="failures", color="bank",
                              title="Failure reasons"), use_container_width=True)

st.subheader("Anomaly alerts")
alerts = query("""SELECT bucket_start AS hour_utc,kind,bank,severity,metric,baseline,message,
    notification_status FROM alerts WHERE bank = ANY(%s) ORDER BY bucket_start DESC LIMIT 100""", (selected,))
if alerts.empty:
    st.info("No alerts yet. Run a demo with DEMO_INCIDENTS=true.")
else:
    st.dataframe(alerts, use_container_width=True, hide_index=True)

st.subheader("Recent ingestion runs")
logs = query("""SELECT started_at,source,input_rows,accepted_rows,duplicate_rows,rejected_rows,status
    FROM ingestion_runs ORDER BY started_at DESC LIMIT 15""")
st.dataframe(logs, use_container_width=True, hide_index=True)
st.caption("Refresh the browser to request fresh data; SQL results are cached for up to 60 seconds.")


st.subheader("Data quality & freshness")
quality = query("""SELECT COUNT(*)::int AS runs,
    COALESCE(SUM(input_rows),0)::bigint AS input_rows,
    COALESCE(SUM(accepted_rows),0)::bigint AS accepted_rows,
    COALESCE(SUM(duplicate_rows),0)::bigint AS duplicate_rows,
    COALESCE(SUM(rejected_rows),0)::bigint AS rejected_rows
    FROM ingestion_runs""").iloc[0]
latest = query("SELECT MAX(event_ts) AS latest_event_utc FROM upi_transactions").iloc[0]
qcols = st.columns(4)
for c, label, value in zip(qcols,
    ["Pipeline runs", "Valid imports", "Duplicates avoided", "Rejected records"],
    [int(quality.runs), int(quality.accepted_rows), int(quality.duplicate_rows), int(quality.rejected_rows)]):
    c.metric(label, f"{value:,}")
st.caption(f"Latest payment event (UTC): {latest.latest_event_utc}")

st.subheader("Incident investigation")
try:
    incidents = query("""SELECT id,bank,kind,severity,incident_status,assignee,created_at,
        acknowledged_at,resolved_at,message FROM v_incident_timeline
        WHERE bank = ANY(%s) ORDER BY created_at DESC LIMIT 100""", (selected,))
    st.dataframe(incidents, use_container_width=True, hide_index=True)
except psycopg.Error:
    st.info("Apply the latest schema migration to enable incident workflow.")
