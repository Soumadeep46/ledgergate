from __future__ import annotations
import os
from core.models import Case

try:
    import anthropic
    _CLIENT_AVAILABLE = True
except ImportError:
    _CLIENT_AVAILABLE = False


def _get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not _CLIENT_AVAILABLE:
        return None
    return anthropic.Anthropic(api_key=api_key)


def generate_review_brief(case: Case, name_mismatch: dict | None) -> str:
    client = _get_client()
    if client is None:
        return _fallback_review_brief(case, name_mismatch)

    prompt = (
        f"Case {case.case_id}: legal name '{name_mismatch.get('legal_name')}' vs "
        f"trade name '{name_mismatch.get('trade_name')}'. "
        "Write a 2-sentence review brief for a human compliance reviewer explaining "
        "the likely reason for the mismatch and a recommended next step. "
        "Do not approve or reject the case yourself."
    ) if name_mismatch else f"Case {case.case_id}: summarize why this needs human review in 2 sentences."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception:
        return _fallback_review_brief(case, name_mismatch)


def _fallback_review_brief(case: Case, name_mismatch: dict | None) -> str:
    if name_mismatch:
        return (
            f"Case {case.case_id} flagged for name mismatch between legal name "
            f"'{name_mismatch.get('legal_name')}' and trade name "
            f"'{name_mismatch.get('trade_name')}'. Likely a trade-name variation of the "
            "same entity, but requires human confirmation before proceeding."
        )
    return (
        f"Case {case.case_id} has an unresolved rule failure requiring human judgment. "
        "Recommend manual review of submitted evidence before any decision."
    )


def explain_document_issue(doc_type: str, issue: str, detail: str) -> str:
    client = _get_client()
    if client is None:
        return f"{doc_type.replace('_', ' ').title()} issue: {detail}"

    prompt = f"In one short sentence, explain to a merchant why their {doc_type} was flagged: {detail}"
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception:
        return f"{doc_type.replace('_', ' ').title()} issue: {detail}"