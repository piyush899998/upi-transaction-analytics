# Power BI Web: advanced report build guide (Mac-compatible)

This project stores its canonical data in PostgreSQL. The Power BI service requires a supported connection / gateway, licensing, and tenant permissions for direct refresh, so **there is no guarantee of browser-only direct PostgreSQL refresh**. Start with repeatable PostgreSQL-generated CSV exports; switch to a supported gateway or cloud connector after deployment.

## Prepare your datasets

1. Run `docker compose up --build -d` (requires Docker Desktop).
2. Run `docker compose exec worker python -m upi_analytics.cli export-powerbi --output data/powerbi`.
3. Exports live inside the worker container; copy them out with `docker compose cp worker:/app/data/powerbi ./data/powerbi` (container workdir may differ if customized).
4. At https://app.powerbi.com, use **New report** / upload to create a semantic model from `transactions.csv` (tenant UI varies).
5. Import the other exports if your account supports adding more tables, or build the basic pages from the `transactions` table first.

> `transactions.csv` can contain hundreds of thousands of demo rows. For browser uploads, use a smaller history (`SIMULATION_TXNS_PER_BANK_HOUR=10` and recreate the demo) if your account hits resource limits.

## Page 1: Operations Overview

Cards: Total Transactions, Success Rate %, Successful Value INR, Failed Transactions. Use date slicer, bank slicer; line chart event_ts by count; clustered bar bank by count/status; stacked bar merchant_category by status.

## Page 2: Failure Diagnostics

Slicer bank/status/date; filter FAILED; bar failure_reason by count; matrix bank × merchant_category with count and Failure Rate %; line chart event_ts vs Failed Transactions; drill into hour-level failure spikes.

## Page 3: Incidents & Data Quality

Upload `incidents.csv` and `data_quality.csv` (or use authorized PostgreSQL access through a configured gateway). Cards for open/critical alerts; table incident status + assignee + message; ingestion trends with duplicates, rejects and freshness.

## Modeling and precautions

- Explicitly set `event_ts` as Date/Time with time-zone semantics according to the BI model and `amount_inr` as decimal currency.
- The DAX in `measures.dax` assumes table name `upi_transactions`: rename your uploaded table accordingly or adjust references.
- Rates are measured over **resolved** transactions unless specifically named otherwise.
- Do not upload real payments, credentials, SMTP details or PostgreSQL connection strings to public workspaces.
- Publishing, scheduled refresh and sharing may require additional Power BI/Fabric licensing. No `.pbix` file is included.
