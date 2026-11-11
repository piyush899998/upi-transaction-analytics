"""SMTP notifications; unsent alerts remain in PostgreSQL for later retry."""
from email.message import EmailMessage
import logging
import smtplib
import ssl
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from psycopg import Connection
from .config import Settings

logger = logging.getLogger(__name__)


def send_email(cfg: Settings, subject: str, message: str) -> None:
    if not cfg.smtp_ready():
        raise RuntimeError("SMTP is not configured; see .env.example")
    mail = EmailMessage()
    mail["From"] = cfg.smtp_from
    mail["To"] = cfg.alert_to
    mail["Subject"] = subject
    mail.set_content(message)
    if cfg.smtp_ssl:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15, context=ssl.create_default_context()) as smtp:
            smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.send_message(mail)
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.send_message(mail)


def notify_pending(conn: "Connection", cfg: Settings, max_attempts: int = 3) -> dict:
    summary = {"sent": 0, "failed": 0, "skipped_unconfigured": 0}
    if not cfg.smtp_ready():
        logger.warning("SMTP not configured: alerts retained in database; dashboard still shows them")
        summary["skipped_unconfigured"] = 1
        return summary
    # Single-worker deployment. FOR UPDATE SKIP LOCKED allows scaling later.
    with conn.transaction():
        rows = conn.execute("""SELECT id,kind,bank,bucket_start,severity,message FROM alerts
            WHERE notification_status IN ('PENDING','FAILED') AND notification_attempts < %s
            ORDER BY created_at ASC LIMIT 100 FOR UPDATE SKIP LOCKED""", (max_attempts,)).fetchall()
        for alert_id, kind, bank, bucket, severity, msg in rows:
            try:
                send_email(cfg, f"[{severity}] UPI {kind}: {bank}",
                    f"Simulated UPI Transaction Monitoring\n\nUTC Hour: {bucket.isoformat()}\n\n{msg}\n\nThis is synthetic demonstration data.")
                conn.execute("""UPDATE alerts SET notification_status='SENT',notification_attempts=notification_attempts+1,
                         notified_at=now(),notification_error=NULL WHERE id=%s""", (alert_id,))
                summary["sent"] += 1
            except (OSError, smtplib.SMTPException, RuntimeError, ValueError) as exc:
                # Do not save potentially sensitive SMTP response bodies or credentials.
                logger.warning("Email notification failed for alert %s (%s)", alert_id, type(exc).__name__)
                conn.execute("""UPDATE alerts SET notification_status='FAILED',notification_attempts=notification_attempts+1,
                         notification_error=%s WHERE id=%s""", (type(exc).__name__, alert_id))
                summary["failed"] += 1
    return summary
