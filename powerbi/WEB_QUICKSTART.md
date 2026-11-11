# Power BI Web: advanced report build guide (Mac-compatible)

The canonical data is PostgreSQL. Browser-only direct PostgreSQL refresh is not guaranteed; Power BI Service may require a supported gateway, tenant permissions, and licensing. Begin with reproducible CSV exports from PostgreSQL.

## Prepare datasets

1. Run `docker compose up --build -d`.
2. Run `docker compose exec worker python -m upi_analytics.cli export-powerbi --output data/powerbi`.
3. Copy exports: `docker compose cp worker:/app/data/powerbi ./data/powerbi`.
4. In https://app.powerbi.com create a report from `transactions.csv`.
5. Add `incidents.csv` and `data_quality.csv` where supported.

## Report pages

**Operations Overview:** Total Transactions, Success Rate, Successful Value INR, Failed Transactions, time trend, bank/status breakdown, merchant categories.

**Failure Diagnostics:** Failure reasons, bank × category matrix, hourly failures, date and bank slicers.

**Incidents & Data Quality:** Open/critical incidents, incident lifecycle table, duplicates, rejects, freshness.

## Important

Set `event_ts` as Date/Time and `amount_inr` as decimal currency. The DAX assumes table `upi_transactions`; rename the imported table or adjust measures. No `.pbix` is included. Never upload real payment data or credentials.
