from __future__ import annotations

from core.models import Case, CaseState, ExceptionType

TAKE_RATE = 0.02
HOURS_IN_MONTH = 720

RECOVERED_STATUSES = {"resolved", "recovered"}
HUMAN_REVIEW_STATUSES = {
    "human_review",
    "awaiting_evidence",
    "escalated",
}
COMPLIANCE_STOPPED_STATUSES = {
    "compliance_stop",
    "stopped",
}


def estimated_revenue(case: Case, resolution_hours: float) -> float:
    if case.state in (CaseState.REJECTED, CaseState.ESCALATED):
        return 0.0

    if case.exception_type == ExceptionType.HARD_COMPLIANCE_BLOCK:
        return 0.0

    time_saved = max(case.baseline_hours - resolution_hours, 0.0)
    gmv = case.merchant.monthly_gmv

    return gmv * TAKE_RATE * (time_saved / HOURS_IN_MONTH) * case.confidence


def gmv_at_risk(cases: list[Case]) -> float:
    unresolved = (
        CaseState.RECEIVED,
        CaseState.PROCESSING,
        CaseState.NEEDS_EVIDENCE,
        CaseState.REVALIDATING,
        CaseState.READY_FOR_REVIEW,
        CaseState.ESCALATED,
    )

    return sum(
        c.merchant.monthly_gmv
        for c in cases
        if c.state in unresolved
    )


def resolution_hours(case: Case) -> float:
    if not case.resolved_at:
        return 0.0

    delta = case.resolved_at - case.created_at
    return delta.total_seconds() / 3600


def average_resolution_time(cases: list[Case]) -> float:
    resolved = [
        c
        for c in cases
        if c.resolved_at is not None
    ]

    if not resolved:
        return 0.0

    total = sum(resolution_hours(c) for c in resolved)
    return total / len(resolved)


def confirmed_revenue_unlocked(cases: list[Case]) -> float:
    total = 0.0

    for c in cases:
        if (
            c.cohort == "SAFE"
            and c.state == CaseState.REVENUE_UNLOCKED
            and c.confidence >= 1.0
        ):
            total += estimated_revenue(
                c,
                resolution_hours(c),
            )

    return total


def total_estimated_revenue(cases: list[Case]) -> float:
    total = 0.0

    for c in cases:
        if c.resolved_at:
            total += estimated_revenue(
                c,
                resolution_hours(c),
            )

    return total


def compliance_overrides(cases: list[Case]) -> int:
    return sum(
        1
        for c in cases
        if (
            c.exception_type == ExceptionType.HARD_COMPLIANCE_BLOCK
            and c.state in (
                CaseState.APPROVED,
                CaseState.REVENUE_UNLOCKED,
            )
        )
    )


def total_revenue_blocked_cases(cases: list[Case]) -> int:
    return sum(
        1
        for c in cases
        if c.cohort in (
            "SAFE",
            "AMBIGUOUS",
            "HARD",
        )
    )


def automatically_resolved_cases(cases: list[Case]) -> int:
    return sum(
        1
        for c in cases
        if (
            c.cohort == "SAFE"
            and c.recovery_status in RECOVERED_STATUSES
            and c.state == CaseState.REVENUE_UNLOCKED
        )
    )


def human_review_cases(cases: list[Case]) -> int:
    return sum(
        1
        for c in cases
        if (
            c.cohort == "AMBIGUOUS"
            and c.recovery_status in HUMAN_REVIEW_STATUSES
        )
    )


def compliance_stopped_cases(cases: list[Case]) -> int:
    return sum(
        1
        for c in cases
        if (
            c.cohort == "HARD"
            and c.recovery_status in COMPLIANCE_STOPPED_STATUSES
        )
    )


def recovery_attempts(cases: list[Case]) -> int:
    return sum(
        c.recovery_attempts
        for c in cases
    )


def successful_synthetic_recoveries(cases: list[Case]) -> int:
    return sum(
        1
        for c in cases
        if (
            c.cohort == "SAFE"
            and c.recovery_status in RECOVERED_STATUSES
            and c.state == CaseState.REVENUE_UNLOCKED
            and c.estimated_recovered_revenue > 0.0
        )
    )


def recovery_rate(cases: list[Case]) -> float:
    eligible_cases = [
        c
        for c in cases
        if c.cohort == "SAFE"
    ]

    if not eligible_cases:
        return 0.0

    successful_cases = successful_synthetic_recoveries(cases)

    return successful_cases / len(eligible_cases)


def estimated_recovered_revenue(cases: list[Case]) -> float:
    return sum(
        c.estimated_recovered_revenue
        for c in cases
        if (
            c.cohort == "SAFE"
            and c.recovery_status in RECOVERED_STATUSES
            and c.state == CaseState.REVENUE_UNLOCKED
        )
    )


def recovery_summary(cases: list[Case]) -> dict:
    return {
        "total_revenue_blocked_cases": total_revenue_blocked_cases(cases),
        "automatically_resolved_cases": automatically_resolved_cases(cases),
        "human_review_cases": human_review_cases(cases),
        "compliance_stopped_cases": compliance_stopped_cases(cases),
        "recovery_attempts": recovery_attempts(cases),
        "successful_synthetic_recoveries": successful_synthetic_recoveries(cases),
        "recovery_rate": recovery_rate(cases),
        "estimated_recovered_revenue": estimated_recovered_revenue(cases),
        "compliance_overrides": compliance_overrides(cases),
    }


def fifo_baseline_hours(cases: list[Case]) -> float:
    if not cases:
        return 0.0

    return sum(
        c.baseline_hours
        for c in cases
    ) / len(cases)


def benchmark_summary(cases: list[Case]) -> dict:
    summary = {
        "fifo_baseline_avg_hours": fifo_baseline_hours(cases),
        "LedgerGate_avg_hours": average_resolution_time(cases),
        "gmv_at_risk": gmv_at_risk(cases),
        "estimated_revenue_unlocked": total_estimated_revenue(cases),
        "confirmed_revenue_unlocked": confirmed_revenue_unlocked(cases),
        "compliance_overrides": compliance_overrides(cases),
    }

    summary.update(recovery_summary(cases))

    return summary