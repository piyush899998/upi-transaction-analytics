"""Fully runnable dashboard for local or Docker deployment; Power BI assets also included."""
import os
import pandas as pd
import plotly.express as px
import streamlit as st
import psycopg
from psycopg.rows import dict_row

st.set_page_config(page_title="UPI Payment Intelligence", page_icon="📊", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1450px;padding-top:2rem}
[data-testid="stMetric"] {background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--text-color) 12%,transparent);border-radius:12px;padding:16px}
[data-testid="stMetric"] [data-testid="stMetricLabel"],[data-testid="stMetric"] [data-testid="stMetricValue"] {color:var(--text-color)!important}
[data-testid="stMetric"] [data-testid="stMetricValue"] {font-weight:650}
[data-testid="stVerticalBlock"] {min-width:0}
h1,h2,h3 {letter-spacing:-.025em}
</style>""", unsafe_allow_html=True)
st.title("Payment operations")
st.caption("Synthetic UPI transactions  ·  UTC timestamps  ·  Operations intelligence")

BANK_COLORS = {"AXIS":"#4f46e5","HDFC":"#0891b2","ICICI":"#d97706","SBI":"#059669"}
def clean_chart(fig, *, percent=False, horizontal=False):
    # Let Streamlit supply theme-aware font and background colors.
    # Legends sit BELOW the plotting area to prevent overlap with bars and titles.
    fig.update_layout(
        template="none", height=380,
        margin=dict(l=14, r=20, t=66, b=100),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        title=dict(font=dict(size=15), x=0, xanchor="left", y=0.98),
        legend=dict(orientation="h", x=0, xanchor="left",
                    y=-0.28, yanchor="top", title_text="",
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="closest" if horizontal else "x unified",
        bargap=0.4,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, title_text="",
                     automargin=True, tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.16)",
                     zeroline=False, title_text="", automargin=True,
                     tickfont=dict(size=11),
                     tickformat=".0f" if percent else "~s")
    if percent:
        fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    if horizontal:
        fig.update_xaxes(tickformat="~s", showgrid=True,
                         gridcolor="rgba(128,128,128,0.16)")
        fig.update_yaxes(showgrid=False)
        fig.update_layout(margin=dict(l=20,r=20,t=66,b=55))
    if not fig.layout.showlegend and fig.layout.showlegend is not None:
        fig.update_layout(margin=dict(l=14,r=20,t=66,b=60))
    return fig


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

st.sidebar.header("Filters")
selected = st.sidebar.multiselect("Bank segments", banks.bank.tolist(), default=banks.bank.tolist())
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
    ["Transactions", "Success rate · resolved", "Failed", "Pending", "Successful value"],
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
    if days > 7:
        hourly["period"] = pd.to_datetime(hourly["hour_utc"], utc=True).dt.floor("D")
        chart_data = hourly.groupby(["period","bank"], as_index=False)[["transactions","failures","resolved"]].sum()
        chart_data["failure_rate_pct"] = (chart_data.failures / chart_data.resolved.replace(0,float("nan")) * 100).fillna(0)
        cadence = "Daily"
    else:
        chart_data = hourly.rename(columns={"hour_utc":"period"})
        cadence = "Hourly"
    st.subheader("Traffic & reliability")
    st.caption(f"{cadence} trends · {days}-day window · Hover for exact values")
    left, right = st.columns(2, gap="large")
    with left:
        fig = px.line(chart_data,x="period",y="transactions",color="bank",
            color_discrete_map=BANK_COLORS,title="Transaction volume")
        fig.update_traces(line=dict(width=2.2))
        st.plotly_chart(clean_chart(fig),use_container_width=True,theme="streamlit")
    with right:
        fig = px.line(chart_data,x="period",y="failure_rate_pct",color="bank",
            color_discrete_map=BANK_COLORS,title="Failure rate · resolved transactions")
        fig.update_traces(line=dict(width=2.2))
        st.plotly_chart(clean_chart(fig,percent=True),use_container_width=True,theme="streamlit")

bank_summary = query(f"""SELECT bank,COUNT(*)::int AS transactions,
    COUNT(*) FILTER (WHERE status='FAILED')::int AS failures,
    COUNT(*) FILTER (WHERE status='SUCCESS')::int AS successes
    FROM upi_transactions {where} GROUP BY bank ORDER BY bank""", params)
reason_summary = query(f"""SELECT bank,failure_reason,COUNT(*)::int AS failures
    FROM upi_transactions {where} AND status='FAILED' GROUP BY 1,2 ORDER BY failures DESC""", params)
st.subheader("Bank performance")
st.caption("Transaction outcomes and leading failure reasons")
left, right = st.columns(2,gap="large")
with left:
    long = bank_summary.melt(id_vars="bank",value_vars=["successes","failures"],
        var_name="status",value_name="count")
    fig = px.bar(long,x="bank",y="count",color="status",barmode="stack",
        color_discrete_map={"successes":"#059669","failures":"#ef6b6b"},
        title="Resolved transactions by bank")
    fig.update_layout(bargap=.45)
    st.plotly_chart(clean_chart(fig),use_container_width=True,theme="streamlit")
with right:
    if not reason_summary.empty:
        top = reason_summary.groupby("failure_reason",as_index=False)["failures"].sum()
        top = top.nlargest(7,"failures").sort_values("failures")
        fig = px.bar(top,x="failures",y="failure_reason",orientation="h",
            color_discrete_sequence=["#64748b"],title="Top failure reasons")
        fig.update_layout(showlegend=False,bargap=.4)
        st.plotly_chart(clean_chart(fig,horizontal=True),use_container_width=True,theme="streamlit")
    else:
        st.info("No failures recorded for this selection.")

st.subheader("Anomaly alerts")
st.caption("Recent alerts across selected bank segments")
alerts = query("""SELECT bucket_start AS hour_utc,kind,bank,severity,metric,baseline,message,
    notification_status FROM alerts WHERE bank = ANY(%s) ORDER BY bucket_start DESC LIMIT 100""", (selected,))
if alerts.empty:
    st.info("No alerts yet. Run a demo with DEMO_INCIDENTS=true.")
else:
    st.dataframe(alerts, use_container_width=True, hide_index=True)

st.subheader("Recent ingestion runs")
st.caption("Pipeline audit history")
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
