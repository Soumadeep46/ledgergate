from __future__ import annotations
from core.models import ExceptionType, RiskLevel, RuleResult

HARD_BLOCK_RULES = {"GSTIN_STATUS", "RESTRICTED_ENTITY_SCREEN"}
AMBIGUOUS_RULES = {"BANK_NAME_MATCH", "LEGAL_TRADE_NAME_MATCH"}
SAFE_REMEDIATION_RULES = {"PAN_FORMAT", "GSTIN_FORMAT", "GSTIN_PAN_LINK"}


def classify(
    case_dict: dict,
    rule_results: list[RuleResult],
    has_document_issues: bool,
) -> tuple[ExceptionType, RiskLevel]:
    failed = {r.rule_name for r in rule_results if not r.passed}

    # Hard compliance always wins — no GMV, no confidence, no override.
    if failed & HARD_BLOCK_RULES:
        return ExceptionType.HARD_COMPLIANCE_BLOCK, RiskLevel.HIGH

    if case_dict.get("hard_issue"):
        return ExceptionType.HARD_COMPLIANCE_BLOCK, RiskLevel.HIGH

    # Ambiguous — soft name/bank mismatches need human judgment.
    if failed & AMBIGUOUS_RULES:
        return ExceptionType.AMBIGUOUS_REVIEW, RiskLevel.MEDIUM

    # Safe — document quality issues or format-only failures, machine-fixable.
    if has_document_issues or (failed & SAFE_REMEDIATION_RULES):
        return ExceptionType.SAFE_TO_REMEDIATE, RiskLevel.LOW

    if failed:
        # any unexpected failure defaults to human review, never silent pass
        return ExceptionType.AMBIGUOUS_REVIEW, RiskLevel.MEDIUM

    return ExceptionType.CLEAN_APPROVAL, RiskLevel.LOW


def priority_score(monthly_gmv: float, exception_type: ExceptionType) -> float:
    """
    GMV affects queue ORDER only. Never used in classify() above,
    never changes exception_type or unblocks HARD_COMPLIANCE_BLOCK.
    """
    if exception_type == ExceptionType.HARD_COMPLIANCE_BLOCK:
        return 0.0  # hard blocks never get GMV-based priority boost
    return monthly_gmv