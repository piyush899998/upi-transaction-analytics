"""Configuration and centralized thresholds. Credentials never logged."""
from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://upi:upi_local_dev@localhost:5432/upi_analytics")
    seed: int = int(os.getenv("SIMULATION_SEED", "20261111"))
    days: int = int(os.getenv("SIMULATION_DAYS", "90"))
    per_bank_hour: int = int(os.getenv("SIMULATION_TXNS_PER_BANK_HOUR", "36"))
    demo_incidents: bool = env_bool("DEMO_INCIDENTS", True)
    simulate_live_data: bool = env_bool("SIMULATE_LIVE_DATA", True)
    scheduler_seconds: int = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "900"))
    failure_threshold: float = float(os.getenv("FAILURE_RATE_THRESHOLD", "0.18"))
    failure_min_txns: int = int(os.getenv("FAILURE_MIN_TXNS", "20"))
    failure_multiplier: float = float(os.getenv("FAILURE_MULTIPLIER", "2.5"))
    failure_min_abs_increase: float = float(os.getenv("FAILURE_MIN_ABS_INCREASE", "0.08"))
    volume_drop_ratio: float = float(os.getenv("VOLUME_DROP_RATIO", "0.55"))
    volume_min_baseline: int = int(os.getenv("VOLUME_MIN_BASELINE", "20"))
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    alert_to: str = os.getenv("ALERT_TO", "")
    smtp_ssl: bool = env_bool("SMTP_USE_SSL", True)

    def smtp_ready(self) -> bool:
        return all((self.smtp_host, self.smtp_username, self.smtp_password, self.smtp_from, self.alert_to))

    def validate(self) -> None:
        if not 1 <= self.days <= 365 or not 1 <= self.per_bank_hour <= 10000:
            raise ValueError("SIMULATION_DAYS must be 1..365 and SIMULATION_TXNS_PER_BANK_HOUR 1..10000")
        if not 0 <= self.failure_threshold <= 1 or not 0 <= self.volume_drop_ratio <= 1:
            raise ValueError("Rate/ratio thresholds must be between 0 and 1")
        if self.scheduler_seconds < 30:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be at least 30")


ROOT = Path(__file__).resolve().parents[2]
