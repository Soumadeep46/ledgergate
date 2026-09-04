from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from core.models import Case

AUDIT_LOG_PATH = Path(__file__).parent.parent / "data" / "audit_log.jsonl"


def log_event(event_type: str, case_id: str, payload: dict) -> dict:
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "case_id": case_id,
        "payload": _sanitize(payload),
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def log_recovery_event(case: Case, event_type: str, payload: dict | None = None) -> dict:
    recovery_payload = {
        "recovery_status": case.recovery_status,
        "recovery_action": case.recovery_action,
        "recovery_attempts": case.recovery_attempts,
        "recovery_reason": case.recovery_reason,
        "estimated_recovered_revenue": case.estimated_recovered_revenue,
    }

    if payload:
        recovery_payload.update(payload)

    return log_event(event_type, case.case_id, recovery_payload)


def _sanitize(payload: dict) -> dict:
    blocked_keys = {"pan", "gstin", "raw_document", "document_content"}
    return {k: v for k, v in payload.items() if k.lower() not in blocked_keys}


def read_audit_log(case_id: str | None = None) -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    entries = []
    with open(AUDIT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if case_id is None or entry.get("case_id") == case_id:
                entries.append(entry)
    return entries


def clear_audit_log() -> None:
    if AUDIT_LOG_PATH.exists():
        AUDIT_LOG_PATH.unlink()