# Power BI connection and dashboard specification

The repository includes a **fully functional Streamlit dashboard** and everything needed to build the Power BI version: PostgreSQL reporting views, Power Query (M) connection templates, DAX measures, a report layout, and refresh guidance. A binary `.pbix`/`.pbit` file is **not** included: Power BI Desktop cannot run in the Linux build environment, and pretending a binary was validated would be misleading.

## Connection

1. Install Power BI Desktop (Windows) and the PostgreSQL/Npgsql driver if prompted.
2. Start the PostgreSQL service (`docker compose up -d db`) and run `docker compose run --rm worker python -m upi_analytics.cli demo`.
3. Power BI Desktop → **Get Data** → PostgreSQL database → Server `localhost:5432`, Database `upi_analytics`, Import mode. Enter user `upi` and the password from `compose.yaml` (change it for nonlocal deployments).
4. In Navigator, import `v_daily_kpis`, `v_hourly_bank_kpis`, `v_bank_kpis`, `v_failure_reasons`, and `alerts`. You may also import `upi_transactions` for row-level drilldowns.
5. Set `v_daily_kpis[day_ist]` to **Date**; `v_hourly_bank_kpis[hour_utc]` and `alerts[bucket_start]` to Date/Time; numeric count columns to whole number; values to decimal/currency.
6. Paste the optional DAX measures from `measures.dax` into Power BI (create one measure at a time). All datasets are simulated; report should say so.

## Suggested report pages

- **Operations overview:** cards Total Transactions, Success Rate, Failure Rate, Successful Payment Value; line chart Day vs Total Transactions; clustered bar Bank vs Total Transactions.
- **Failure diagnostics:** bar Bank vs Failure Rate; stacked bar Bank × Failure Reason; hourly line trend by bank; status counts.
- **Alerts & pipeline health:** alert table with severity, bank, UTC hour, anomaly, baseline, metric and email delivery status; ingestion run quality table and trend.

> For aggregate KPIs across banks/hours, **recalculate success/failure rates from summed counts**. Do not average percentages.

## Refresh automation

- Power BI Desktop: **Home → Refresh** to import the latest PostgreSQL values locally.
- Power BI Service: publish the PBIX from Desktop; provision a reachable PostgreSQL server and, where necessary, an **on-premises data gateway** with a configured PostgreSQL data source and credentials. Enable scheduled refresh subject to your Microsoft license and gateway connectivity.
- Import mode does not update without a refresh. The worker automatically updates PostgreSQL, and the included Streamlit dashboard polls changes on each browser rerun (up to 60s cache). Power BI scheduled refresh is an **external configuration step**, not a capability implemented by Python in this repository.
- Never expose port 5432 publicly or embed secrets in report files.

See `connection.m` for an optional Advanced Editor template. Power BI may need the PostgreSQL driver depending on installed version.
