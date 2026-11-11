"""PostgreSQL connection and schema bootstrap."""
from pathlib import Path
import psycopg
from .config import ROOT, Settings


def connect(cfg: Settings):
    return psycopg.connect(cfg.database_url, connect_timeout=10)


def initialize(cfg: Settings) -> None:
    schema = (ROOT / "sql" / "001_schema.sql").read_text(encoding="utf8")
    with connect(cfg) as conn:
        conn.execute(schema)
