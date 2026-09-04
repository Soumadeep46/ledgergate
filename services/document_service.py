from __future__ import annotations
from core.models import DocumentIssue


def extract_document_issues(case_dict: dict) -> list[DocumentIssue]:
    issues = []
    for raw in case_dict.get("document_issues", []):
        issues.append(
            DocumentIssue(
                doc_type=raw["doc_type"],
                issue=raw["issue"],
                detail=raw["detail"],
            )
        )
    return issues


def simulate_field_extraction(case_dict: dict) -> dict:
    m = case_dict["merchant"]
    return {
        "extracted_legal_name": m["legal_name"],
        "extracted_trade_name": m["trade_name"],
        "extracted_pan": m["pan"],
        "extracted_gstin": m["gstin"],
        "extracted_bank_name": m["bank_account_name"],
        "extraction_confidence": 0.95 if not case_dict.get("document_issues") else 0.6,
    }


def explain_issue(issue: DocumentIssue) -> str:
    return f"{issue.doc_type.replace('_', ' ').title()} flagged as {issue.issue.replace('_', ' ').lower()}: {issue.detail}"


def document_hash(document_id: str) -> str:
    import hashlib
    return hashlib.sha256(document_id.encode()).hexdigest()[:16]