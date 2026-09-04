from __future__ import annotations
import secrets
from datetime import datetime
from core.models import Case, CaseState, DocumentIssue, ExceptionType


MAX_EVIDENCE_ATTEMPTS = 2
MAX_AUTOMATED_CORRECTIONS = 1


def generate_correction_message(issue: DocumentIssue) -> str:
    return (
        f"Your {issue.doc_type.replace('_', ' ').title()} could not be verified "
        f"because of: {issue.detail}. Please upload a clearer copy."
    )


def generate_secure_token() -> str:
    return secrets.token_urlsafe(16)


def get_recovery_policy(case: Case) -> dict:
    if case.exception_type == ExceptionType.HARD_COMPLIANCE_BLOCK:
        return {
            "allowed": False,
            "action": "escalate_human_review",
            "reason": "Hard compliance issue cannot be automatically remediated",
        }

    if case.exception_type == ExceptionType.AMBIGUOUS_REVIEW:
        return {
            "allowed": False,
            "action": "escalate_human_review",
            "reason": "Ambiguous issue requires human review",
        }

    if case.exception_type == ExceptionType.SAFE_TO_REMEDIATE:
        return {
            "allowed": True,
            "action": "request_correction",
            "reason": "Safe document issue is eligible for bounded recovery",
        }

    return {
        "allowed": False,
        "action": "stop_recovery",
        "reason": "Case is not eligible for automated recovery",
    }


def can_continue_recovery(case: Case) -> bool:
    policy = get_recovery_policy(case)

    if not policy["allowed"]:
        case.recovery_status = (
            "compliance_stop"
            if case.exception_type == ExceptionType.HARD_COMPLIANCE_BLOCK
            else "human_review"
            if case.exception_type == ExceptionType.AMBIGUOUS_REVIEW
            else "stopped"
        )
        case.recovery_action = policy["action"]
        case.recovery_reason = policy["reason"]
        return False

    if case.recovery_attempts >= MAX_EVIDENCE_ATTEMPTS:
        case.recovery_status = "stopped"
        case.recovery_action = "stop_recovery"
        case.recovery_reason = "Maximum evidence attempts exceeded"
        return False

    if (
        case.recovery_action == "request_correction"
        and case.recovery_attempts >= MAX_AUTOMATED_CORRECTIONS
    ):
        case.recovery_status = "stopped"
        case.recovery_action = "stop_recovery"
        case.recovery_reason = (
            "Maximum automated correction actions exceeded"
        )
        return False

    return True


def send_correction_request(case: Case) -> dict:
    if not case.document_issues:
        return {"sent": False, "reason": "No document issues to remediate"}

    if not can_continue_recovery(case):
        return {
            "sent": False,
            "case_id": case.case_id,
            "reason": case.recovery_reason,
            "recovery_status": case.recovery_status,
        }

    issue = case.document_issues[0]
    message = generate_correction_message(issue)
    token = generate_secure_token()

    case.recovery_attempts += 1
    case.recovery_action = "request_correction"
    case.recovery_status = "correction_requested"
    case.recovery_reason = "Correction request sent"

    case.transition(
        CaseState.NEEDS_EVIDENCE,
        f"Correction requested for {issue.doc_type}",
    )

    return {
        "sent": True,
        "case_id": case.case_id,
        "message": message,
        "token": token,
        "issued_at": datetime.utcnow().isoformat(),
        "recovery_status": case.recovery_status,
        "recovery_attempts": case.recovery_attempts,
    }


def upload_replacement(case: Case, document_id: str) -> dict:
    if not can_continue_recovery(case):
        return {
            "document_id": document_id,
            "status": "STOPPED",
            "case_id": case.case_id,
            "reason": case.recovery_reason,
            "recovery_status": case.recovery_status,
        }

    case.recovery_status = "revalidating"
    case.recovery_action = "upload_replacement"
    case.recovery_reason = "Replacement evidence uploaded"

    case.transition(
        CaseState.REVALIDATING,
        f"Replacement {document_id} uploaded",
    )

    return {
        "document_id": document_id,
        "status": "UPLOADED",
        "recovery_status": case.recovery_status,
        "recovery_attempts": case.recovery_attempts,
    }


def rerun_verification(case: Case, passed: bool) -> dict:
    if case.recovery_status in {
        "stopped",
        "compliance_stop",
        "human_review",
    }:
        return {
            "case_id": case.case_id,
            "passed": False,
            "state": case.state.value,
            "recovery_status": case.recovery_status,
            "reason": case.recovery_reason,
        }

    if passed:
        case.document_issues = []
        case.recovery_status = "resolved"
        case.recovery_action = "rerun_verification"
        case.recovery_reason = "Replacement passed verification"
        case.estimated_recovered_revenue = case.merchant.monthly_gmv
        case.transition(
            CaseState.APPROVED,
            "Replacement passed verification",
        )
        case.confidence = 0.7
    else:
        case.recovery_status = "awaiting_evidence"
        case.recovery_action = "rerun_verification"
        case.recovery_reason = "Replacement still failed verification"

        case.transition(
            CaseState.NEEDS_EVIDENCE,
            "Replacement still failed verification",
        )

        if case.recovery_attempts >= MAX_EVIDENCE_ATTEMPTS:
            case.recovery_status = "stopped"
            case.recovery_action = "stop_recovery"
            case.recovery_reason = "Maximum evidence attempts exceeded"

    return {
        "case_id": case.case_id,
        "passed": passed,
        "state": case.state.value,
        "recovery_status": case.recovery_status,
        "recovery_attempts": case.recovery_attempts,
        "reason": case.recovery_reason,
    }


def delete_temporary_document(case: Case, document_id: str) -> dict:
    return {
        "event": "DOCUMENT_RETENTION_POLICY_APPLIED",
        "case_id": case.case_id,
        "document_id": document_id,
        "verification_status": "PASSED",
        "raw_document_deleted": True,
        "temporary_storage_deleted": True,
        "retention_policy": "DELETE_AFTER_VERIFICATION",
        "actor": "system",
        "timestamp": datetime.utcnow().isoformat(),
    }


def unlock_revenue(case: Case) -> dict:
    case.transition(
        CaseState.REVENUE_UNLOCKED,
        "Merchant activated post-remediation",
    )
    case.confidence = 1.0
    case.resolved_at = datetime.utcnow()

    return {
        "case_id": case.case_id,
        "state": case.state.value,
        "confidence": case.confidence,
    }