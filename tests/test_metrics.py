from datetime import datetime, timedelta, timezone
from core.models import Case, Merchant, CaseState, ExceptionType
from core.metrics import (
    estimated_revenue,
    gmv_at_risk,
    resolution_hours,
    average_resolution_time,
    confirmed_revenue_unlocked,
    total_estimated_revenue,
    compliance_overrides,
    fifo_baseline_hours,
    benchmark_summary,
)


def make_case(
    state,
    exc_type,
    confidence,
    gmv=1_000_000.0,
    hours_ago_created=48,
    hours_ago_resolved=None,
):
    m = Merchant(
        "M-0001",
        "Test Co",
        "Test Co",
        "ABCDE1234F",
        "27ABCDE1234F1Z5",
        "Test Co",
        gmv,
    )

    c = Case("VF-0001", m, "SAFE")

    c.state = state
    c.exception_type = exc_type
    c.confidence = confidence

    c.created_at = datetime.now(timezone.utc) - timedelta(
        hours=hours_ago_created
    )

    if hours_ago_resolved is not None:
        c.resolved_at = datetime.now(timezone.utc) - timedelta(
            hours=hours_ago_resolved
        )

    return c


def test_estimated_revenue_positive_for_resolved_case():
    c = make_case(CaseState.REVENUE_UNLOCKED, ExceptionType.SAFE_TO_REMEDIATE, 1.0, hours_ago_resolved=1)
    rev = estimated_revenue(c, resolution_hours(c))
    assert rev > 0


def test_estimated_revenue_zero_for_rejected():
    c = make_case(CaseState.REJECTED, ExceptionType.HARD_COMPLIANCE_BLOCK, 0.0, hours_ago_resolved=1)
    rev = estimated_revenue(c, resolution_hours(c))
    assert rev == 0.0


def test_estimated_revenue_zero_for_hard_compliance_block():
    c = make_case(CaseState.ESCALATED, ExceptionType.HARD_COMPLIANCE_BLOCK, 0.5, hours_ago_resolved=1)
    rev = estimated_revenue(c, resolution_hours(c))
    assert rev == 0.0


def test_estimated_revenue_zero_for_escalated():
    c = make_case(CaseState.ESCALATED, ExceptionType.AMBIGUOUS_REVIEW, 0.3, hours_ago_resolved=1)
    rev = estimated_revenue(c, resolution_hours(c))
    assert rev == 0.0


def test_gmv_at_risk_only_counts_unresolved():
    resolved = make_case(CaseState.REVENUE_UNLOCKED, ExceptionType.SAFE_TO_REMEDIATE, 1.0, gmv=500_000.0, hours_ago_resolved=1)
    unresolved = make_case(CaseState.NEEDS_EVIDENCE, ExceptionType.SAFE_TO_REMEDIATE, 0.3, gmv=700_000.0)
    total = gmv_at_risk([resolved, unresolved])
    assert total == 700_000.0


def test_average_resolution_time_ignores_unresolved():
    resolved = make_case(CaseState.APPROVED, ExceptionType.CLEAN_APPROVAL, 1.0, hours_ago_created=48, hours_ago_resolved=12)
    unresolved = make_case(CaseState.PROCESSING, ExceptionType.SAFE_TO_REMEDIATE, 0.0)
    avg = average_resolution_time([resolved, unresolved])
    assert avg == resolution_hours(resolved)


def test_confirmed_revenue_requires_full_confidence():
    confirmed = make_case(CaseState.REVENUE_UNLOCKED, ExceptionType.SAFE_TO_REMEDIATE, 1.0, hours_ago_resolved=1)
    pending = make_case(CaseState.APPROVED, ExceptionType.SAFE_TO_REMEDIATE, 0.7, hours_ago_resolved=1)
    total = confirmed_revenue_unlocked([confirmed, pending])
    assert total == estimated_revenue(confirmed, resolution_hours(confirmed))


def test_total_estimated_revenue_excludes_unresolved():
    resolved = make_case(CaseState.APPROVED, ExceptionType.SAFE_TO_REMEDIATE, 0.7, hours_ago_resolved=1)
    unresolved = make_case(CaseState.PROCESSING, ExceptionType.SAFE_TO_REMEDIATE, 0.0)
    total = total_estimated_revenue([resolved, unresolved])
    assert total == estimated_revenue(resolved, resolution_hours(resolved))


def test_compliance_overrides_detects_hard_block_approved():
    bad = make_case(CaseState.APPROVED, ExceptionType.HARD_COMPLIANCE_BLOCK, 1.0, hours_ago_resolved=1)
    count = compliance_overrides([bad])
    assert count == 1


def test_compliance_overrides_zero_when_none():
    good = make_case(CaseState.REVENUE_UNLOCKED, ExceptionType.SAFE_TO_REMEDIATE, 1.0, hours_ago_resolved=1)
    count = compliance_overrides([good])
    assert count == 0


def test_fifo_baseline_hours_average():
    c1 = make_case(CaseState.APPROVED, ExceptionType.CLEAN_APPROVAL, 1.0)
    c1.baseline_hours = 48.0
    c2 = make_case(CaseState.APPROVED, ExceptionType.CLEAN_APPROVAL, 1.0)
    c2.baseline_hours = 24.0
    avg = fifo_baseline_hours([c1, c2])
    assert avg == 36.0


def test_benchmark_summary_has_all_keys():
    c = make_case(CaseState.REVENUE_UNLOCKED, ExceptionType.SAFE_TO_REMEDIATE, 1.0, hours_ago_resolved=1)
    summary = benchmark_summary([c])
    expected_keys = {
        "fifo_baseline_avg_hours",
        "LedgerGate_avg_hours",
        "gmv_at_risk",
        "estimated_revenue_unlocked",
        "confirmed_revenue_unlocked",
        "compliance_overrides",
    }
    assert expected_keys.issubset(summary.keys())