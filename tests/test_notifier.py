from dataclasses import replace
from unittest.mock import patch, MagicMock
from upi_analytics.config import Settings
from upi_analytics.notifier import send_email, notify_pending
import pytest


def test_missing_smtp_config():
    cfg = replace(Settings(), smtp_host="", smtp_username="")
    with pytest.raises(RuntimeError):
        send_email(cfg, "Demo", "Demo")
    assert notify_pending(MagicMock(), cfg)["skipped_unconfigured"] == 1


def test_sends_via_ssl():
    cfg = replace(Settings(), smtp_host="smtp.example.com", smtp_username="user",
                  smtp_password="secret", smtp_from="test@example.com", alert_to="you@example.com")
    with patch("upi_analytics.notifier.smtplib.SMTP_SSL") as mock_smtp:
        send_email(cfg, "Demo", "Body")
        smtp = mock_smtp.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("user", "secret")
        assert smtp.send_message.call_count == 1
