// Template query for Power Query Advanced Editor.
// Default data source is the localhost PostgreSQL service; create a separate query for each view.
// For example, to import hourly bank KPIs:
let
  Source = PostgreSQL.Database("localhost:5432", "upi_analytics"),
  HourlyBankKpis = Source{[Schema="public", Item="v_hourly_bank_kpis"]}[Data]
in
  HourlyBankKpis
