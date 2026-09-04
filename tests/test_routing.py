from core.classifier import classify, priority_score
from core.models import RuleResult, ExceptionType, RiskLevel


def test_hard_compliance_block_on_gstin_inactive():
    rr = [RuleResult("GSTIN_STATUS", False, "inactive")]
    exc, risk = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.HARD_COMPLIANCE_BLOCK
    assert risk == RiskLevel.HIGH


def test_hard_compliance_block_on_restricted_entity():
    rr = [RuleResult("RESTRICTED_ENTITY_SCREEN", False, "match found")]
    exc, risk = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.HARD_COMPLIANCE_BLOCK


def test_hard_compliance_block_via_hard_issue_flag():
    rr = [RuleResult("PAN_FORMAT", True, "ok")]
    exc, risk = classify({"merchant": {}, "hard_issue": "PROHIBITED_CATEGORY"}, rr, False)
    assert exc == ExceptionType.HARD_COMPLIANCE_BLOCK


def test_ambiguous_review_on_bank_name_mismatch():
    rr = [RuleResult("BANK_NAME_MATCH", False, "low similarity")]
    exc, risk = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.AMBIGUOUS_REVIEW
    assert risk == RiskLevel.MEDIUM


def test_ambiguous_review_on_legal_trade_name_mismatch():
    rr = [RuleResult("LEGAL_TRADE_NAME_MATCH", False, "low similarity")]
    exc, risk = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.AMBIGUOUS_REVIEW


def test_safe_to_remediate_on_document_issue():
    rr = [RuleResult("PAN_FORMAT", True, "ok")]
    exc, risk = classify({"merchant": {}}, rr, True)
    assert exc == ExceptionType.SAFE_TO_REMEDIATE
    assert risk == RiskLevel.LOW


def test_safe_to_remediate_on_format_failure():
    rr = [RuleResult("GSTIN_FORMAT", False, "bad format")]
    exc, risk = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.SAFE_TO_REMEDIATE


def test_clean_approval_when_all_pass():
    rr = [RuleResult("PAN_FORMAT", True, "ok")]
    exc, risk = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.CLEAN_APPROVAL


def test_hard_block_takes_priority_over_ambiguous():
    rr = [
        RuleResult("GSTIN_STATUS", False, "inactive"),
        RuleResult("BANK_NAME_MATCH", False, "low similarity"),
    ]
    exc, _ = classify({"merchant": {}}, rr, False)
    assert exc == ExceptionType.HARD_COMPLIANCE_BLOCK


def test_hard_block_takes_priority_over_safe():
    rr = [RuleResult("RESTRICTED_ENTITY_SCREEN", False, "match")]
    exc, _ = classify({"merchant": {}}, rr, True)
    assert exc == ExceptionType.HARD_COMPLIANCE_BLOCK


def test_gmv_never_overrides_hard_block():
    rr = [RuleResult("GSTIN_STATUS", False, "inactive")]
    exc, _ = classify({"merchant": {}}, rr, False)
    high_gmv_score = priority_score(5_000_000.0, exc)
    assert exc == ExceptionType.HARD_COMPLIANCE_BLOCK
    assert high_gmv_score == 0.0


def test_priority_score_scales_with_gmv_for_non_hard_cases():
    score_low = priority_score(50_000.0, ExceptionType.SAFE_TO_REMEDIATE)
    score_high = priority_score(5_000_000.0, ExceptionType.SAFE_TO_REMEDIATE)
    assert score_high > score_low