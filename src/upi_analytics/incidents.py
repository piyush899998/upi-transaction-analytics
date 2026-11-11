"""Explicit, auditable incident state changes. No automatic resolution guesses."""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from psycopg import Connection

STATES = {"OPEN", "INVESTIGATING", "RESOLVED"}


def transition(conn: "Connection", alert_id: int, new_status: str,
               assignee: str = "", notes: str = "") -> dict:
    """Update an existing alert with an explicit operational state transition."""
    target = new_status.strip().upper()
    if target not in STATES:
        raise ValueError(f"Unsupported incident status: {target}")
    if alert_id <= 0:
        raise ValueError("alert_id must be positive")
    with conn.transaction():
        row = conn.execute("SELECT incident_status FROM alerts WHERE id=%s FOR UPDATE", (alert_id,)).fetchone()
        if not row:
            raise ValueError("Alert not found")
        current = row[0]
        transitions = {"OPEN": {"INVESTIGATING", "RESOLVED"},
                       "INVESTIGATING": {"RESOLVED", "OPEN"}, "RESOLVED": {"OPEN"}}
        if target != current and target not in transitions[current]:
            raise ValueError(f"Invalid transition: {current} -> {target}")
        result = conn.execute("""UPDATE alerts SET incident_status=%s,
           assignee=COALESCE(NULLIF(%s,''),assignee),
           investigation_notes=COALESCE(NULLIF(%s,''),investigation_notes),
           acknowledged_at=CASE WHEN %s='INVESTIGATING' THEN COALESCE(acknowledged_at,now()) ELSE acknowledged_at END,
           resolved_at=CASE WHEN %s='RESOLVED' THEN now() WHEN %s='OPEN' THEN NULL ELSE resolved_at END
           WHERE id=%s RETURNING id,incident_status,assignee,resolved_at""",
           (target, assignee.strip(), notes.strip(), target, target, target, alert_id)).fetchone()
    return dict(zip(("id", "incident_status", "assignee", "resolved_at"), result))
