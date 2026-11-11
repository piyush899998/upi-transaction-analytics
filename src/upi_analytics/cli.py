"""Command line entry point and scheduling loop."""
import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import time
from .config import Settings
from .db import connect, initialize
from .detection import detect_hour
from .etl import ingest_csv
from .notifier import notify_pending
from .simulator import completed_hour, generate_history, generate_incremental

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def pipeline(cfg: Settings, simulate: bool = True) -> dict:
    bucket = completed_hour()
    generated = None
    if simulate:
        output = Path("data/incremental.csv")
        generated = generate_incremental(output, bucket, cfg.per_bank_hour, cfg.seed, incidents=False)
    else:
        output = Path("data/transactions.csv")
    with connect(cfg) as conn:
        ingested = ingest_csv(conn, output) if output.exists() else None
        anomalies = detect_hour(conn, cfg, bucket)
        emails = notify_pending(conn, cfg)
    return {"hour": bucket.isoformat(), "generated": generated, "ingestion": ingested,
            "detected": [a.__dict__ for a in anomalies], "emails": emails}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simulated UPI transaction analytics")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create tables and SQL views")
    export = sub.add_parser("export-powerbi", help="Export sanitized demo views for Power BI Web")
    export.add_argument("--output", default="data/powerbi")
    sub.add_parser("demo", help="Initialize, generate historical dataset, ingest, detect, and optionally send emails")
    g = sub.add_parser("generate", help="Generate history as CSV")
    g.add_argument("--output", default="data/transactions.csv")
    g.add_argument("--days", type=int, default=None)
    ingest = sub.add_parser("ingest", help="Idempotent import from CSV")
    ingest.add_argument("--input", required=True)
    detect = sub.add_parser("detect", help="Evaluate last completed UTC hour or ISO timestamp")
    detect.add_argument("--hour", default=None)
    sub.add_parser("notify", help="Retry queued SMTP alerts")
    incident = sub.add_parser("incident", help="Set an alert incident state")
    incident.add_argument("--id", type=int, required=True)
    incident.add_argument("--status", choices=["OPEN", "INVESTIGATING", "RESOLVED"], required=True)
    incident.add_argument("--assignee", default="")
    incident.add_argument("--notes", default="")
    run = sub.add_parser("run-cycle", help="Process last completed hour")
    run.add_argument("--no-simulate", action="store_true")
    sub.add_parser("scheduler", help="One-time auto-bootstrap then periodic incremental cycles")
    args = parser.parse_args(argv)
    cfg = Settings()
    cfg.validate()
    if args.command == "init":
        initialize(cfg)
        print("Schema and reporting views created")
    elif args.command == "export-powerbi":
        from .export import export_views
        with connect(cfg) as conn:
            print(json.dumps(export_views(conn, Path(args.output)), indent=2))
    elif args.command == "generate":
        output = Path(args.output)
        print(json.dumps({"path": str(output), "rows": generate_history(output, args.days or cfg.days,
                     cfg.per_bank_hour, cfg.seed, incidents=cfg.demo_incidents)}))
    elif args.command == "demo":
        initialize(cfg)
        path = Path("data/transactions.csv")
        count = generate_history(path, cfg.days, cfg.per_bank_hour, cfg.seed, incidents=cfg.demo_incidents)
        with connect(cfg) as conn:
            stats = ingest_csv(conn, path)
            anomalies = detect_hour(conn, cfg, completed_hour())
            notify = notify_pending(conn, cfg)
        print(json.dumps({"generated": count, "ingestion": stats,
                          "detected": [a.__dict__ for a in anomalies], "emails": notify}, indent=2))
    elif args.command == "ingest":
        with connect(cfg) as conn:
            print(json.dumps(ingest_csv(conn, Path(args.input)), indent=2))
    elif args.command == "detect":
        hour = datetime.fromisoformat(args.hour.replace("Z", "+00:00")) if args.hour else completed_hour()
        with connect(cfg) as conn:
            found = detect_hour(conn, cfg, hour)
        print(json.dumps([a.__dict__ for a in found], indent=2))
    elif args.command == "incident":
        from .incidents import transition
        with connect(cfg) as conn:
            print(json.dumps(transition(conn, args.id, args.status, args.assignee, args.notes), default=str))
    elif args.command == "notify":
        with connect(cfg) as conn:
            print(json.dumps(notify_pending(conn, cfg), indent=2))
    elif args.command == "run-cycle":
        print(json.dumps(pipeline(cfg, not args.no_simulate), indent=2))
    elif args.command == "scheduler":
        initialize(cfg)
        with connect(cfg) as conn:
            has_data = conn.execute("SELECT EXISTS(SELECT 1 FROM upi_transactions LIMIT 1)").fetchone()[0]
        if not has_data:
            log.info("Bootstrapping first-use demonstration dataset")
            path = Path("data/transactions.csv")
            generate_history(path, cfg.days, cfg.per_bank_hour, cfg.seed, incidents=cfg.demo_incidents)
            with connect(cfg) as conn:
                log.info("Initial import: %s", ingest_csv(conn, path))
                log.info("Initial anomalies: %s", detect_hour(conn, cfg, completed_hour()))
                log.info("Initial notifications: %s", notify_pending(conn, cfg))
        while True:
            try:
                log.info("Scheduled cycle: %s", json.dumps(pipeline(cfg, cfg.simulate_live_data)))
            except Exception:
                log.exception("Scheduled cycle failed; next cycle will retry")
            time.sleep(cfg.scheduler_seconds)


if __name__ == "__main__":
    main()
