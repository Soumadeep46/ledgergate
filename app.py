import json
import random
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core.models import Case, Merchant, DocumentIssue, CaseState, ExceptionType, RiskLevel
from core.rules import run_all_rules
from core.classifier import classify, priority_score
from core.remediation import (
    send_correction_request,
    upload_replacement,
    rerun_verification,
    delete_temporary_document,
    unlock_revenue,
)
from core.audit import log_event, read_audit_log
from core.metrics import (
    estimated_revenue,
    resolution_hours,
    average_resolution_time,
    gmv_at_risk,
    benchmark_summary,
    compliance_overrides,
    recovery_summary,
)
from services.document_service import extract_document_issues, explain_issue
from services.ai_service import generate_review_brief

DATA_PATH = Path(__file__).parent / "data" / "generated_cases.json"

FORMAT_RULES = {"PAN_FORMAT", "GSTIN_FORMAT", "GSTIN_PAN_LINK"}
COMPLIANCE_RULES = {"GSTIN_STATUS", "RESTRICTED_ENTITY_SCREEN"}

DEMO_RESERVE_SAFE = 3
DEMO_RESERVE_AMBIGUOUS = 2
DEMO_RESERVE_HARD = 1

st.set_page_config(page_title="LedgerGate", layout="wide")

rng = random.Random(7)


def simulate_safe_resolution(case: Case):
    case.transition(CaseState.NEEDS_EVIDENCE, "Correction requested (simulated)")
    case.recovery_status = "awaiting_evidence"
    case.recovery_action = "request_correction"
    case.recovery_attempts = 1
    case.recovery_reason = "Document issue corrected through synthetic resubmission"
    case.transition(CaseState.REVALIDATING, "Replacement uploaded (simulated)")
    case.recovery_status = "revalidating"
    case.recovery_action = "verify_replacement"
    case.document_issues = []
    case.transition(CaseState.APPROVED, "Replacement passed verification (simulated)")
    case.confidence = 0.7
    case.transition(CaseState.REVENUE_UNLOCKED, "Merchant activated (simulated)")
    case.confidence = 1.0
    case.recovery_status = "resolved"
    case.recovery_action = "unlock_revenue"
    case.recovery_reason = "Replacement passed verification and revenue was unlocked"
    minutes = rng.randint(8, 40)
    case.resolved_at = case.created_at + timedelta(minutes=minutes)
    case.estimated_recovered_revenue = estimated_revenue(case, minutes / 60)


def simulate_ambiguous_resolution(case: Case):
    outcome = rng.choices(["APPROVED", "ESCALATED"], weights=[0.7, 0.3])[0]
    case.transition(CaseState.READY_FOR_REVIEW, "Review brief generated (simulated)")
    case.recovery_attempts = 1
    if outcome == "APPROVED":
        case.transition(CaseState.APPROVED, "Human reviewer approved (simulated)")
        case.confidence = 0.7
        case.recovery_status = "human_review_resolved"
        case.recovery_action = "human_review"
        case.recovery_reason = "Ambiguous name mismatch approved by human reviewer"
    else:
        case.transition(CaseState.ESCALATED, "Human reviewer escalated (simulated)")
        case.confidence = 0.3
        case.recovery_status = "human_review"
        case.recovery_action = "escalate_review"
        case.recovery_reason = "Ambiguous name mismatch requires further review"
    hours = rng.randint(1, 6)
    case.resolved_at = case.created_at + timedelta(hours=hours)


def simulate_hard_resolution(case: Case):
    case.transition(CaseState.REJECTED, f"Hard compliance signal confirmed, rejected: {case.__dict__.get('hard_issue', 'unspecified')} (simulated)")
    case.confidence = 0.0
    case.recovery_status = "compliance_stop"
    case.recovery_action = "compliance_escalation"
    case.recovery_reason = "Hard compliance signal prevents automated recovery"
    hours = rng.randint(2, 10)
    case.resolved_at = case.created_at + timedelta(hours=hours)


@st.cache_resource
def load_cases() -> list[Case]:
    raw_cases = json.loads(DATA_PATH.read_text())
    seen_pans = set()
    cases = []

    safe_reserve_left = DEMO_RESERVE_SAFE
    ambiguous_reserve_left = DEMO_RESERVE_AMBIGUOUS
    hard_reserve_left = DEMO_RESERVE_HARD

    for raw in raw_cases:
        m = raw["merchant"]
        merchant = Merchant(
            merchant_id=m["merchant_id"],
            legal_name=m["legal_name"],
            trade_name=m["trade_name"],
            pan=m["pan"],
            gstin=m["gstin"],
            bank_account_name=m["bank_account_name"],
            monthly_gmv=m["monthly_gmv"],
        )
        case = Case(case_id=raw["case_id"], merchant=merchant, cohort=raw["cohort"])
        case.document_issues = extract_document_issues(raw)

        rule_results = run_all_rules(raw, seen_pans)
        seen_pans.add(m["pan"])
        case.rule_results = rule_results

        exc_type, risk = classify(raw, rule_results, bool(case.document_issues))
        case.exception_type = exc_type
        case.risk_level = risk
        case.transition(CaseState.PROCESSING, "Initial classification complete")

        case.__dict__["hard_issue"] = raw.get("hard_issue")
        case.__dict__["name_mismatch"] = raw.get("name_mismatch")
        case.__dict__["is_demo_interactive"] = False
        case.recovery_status = raw.get("recovery_status", "not_started")
        case.recovery_action = raw.get("recovery_action", "")
        case.recovery_attempts = raw.get("recovery_attempts", 0)
        case.recovery_reason = raw.get("recovery_reason", "")
        case.estimated_recovered_revenue = raw.get("estimated_recovered_revenue", 0.0)

        if exc_type == ExceptionType.CLEAN_APPROVAL:
            case.transition(CaseState.APPROVED, "Clean approval, no exceptions found")
            case.confidence = 1.0
            case.resolved_at = case.created_at

        elif exc_type == ExceptionType.SAFE_TO_REMEDIATE:
            if safe_reserve_left > 0:
                safe_reserve_left -= 1
                case.__dict__["is_demo_interactive"] = True
            else:
                simulate_safe_resolution(case)

        elif exc_type == ExceptionType.AMBIGUOUS_REVIEW:
            if ambiguous_reserve_left > 0:
                ambiguous_reserve_left -= 1
                case.__dict__["is_demo_interactive"] = True
            else:
                simulate_ambiguous_resolution(case)

        elif exc_type == ExceptionType.HARD_COMPLIANCE_BLOCK:
            if hard_reserve_left > 0:
                hard_reserve_left -= 1
                case.__dict__["is_demo_interactive"] = True
            else:
                simulate_hard_resolution(case)

        log_event("CASE_INGESTED", case.case_id, {"cohort": case.cohort, "exception_type": exc_type.value})
        cases.append(case)

    return cases


def cases_to_df(cases: list[Case]) -> pd.DataFrame:
    rows = []
    for c in cases:
        rows.append({
            "Case ID": c.case_id,
            "Merchant": c.merchant.legal_name,
            "Monthly GMV": c.merchant.monthly_gmv,
            "Exception Type": c.exception_type.value if c.exception_type else "-",
            "Risk Level": c.risk_level.value,
            "Status": c.state.value,
            "Priority": priority_score(c.merchant.monthly_gmv, c.exception_type),
            "Demo Case": c.__dict__.get("is_demo_interactive", False),
        })
    return pd.DataFrame(rows)


def find_case(cases: list[Case], case_id: str) -> Case:
    for c in cases:
        if c.case_id == case_id:
            return c
    raise ValueError(f"Case {case_id} not found")


def rule_failure_label(rule_name: str) -> str:
    if rule_name in FORMAT_RULES:
        return "Format/data-entry issue — fixable via resubmission, not a compliance failure"
    if rule_name in COMPLIANCE_RULES:
        return "Confirmed compliance failure — hard block, cannot be auto-remediated"
    return "Soft mismatch — requires human judgment"


cases = load_cases()

st.title("LedgerGate")
st.caption("Compliance-preserving merchant verification and revenue unlock agent — all data synthetic")
st.caption(f"{DEMO_RESERVE_SAFE + DEMO_RESERVE_AMBIGUOUS + DEMO_RESERVE_HARD} cases reserved as live-interactive demo cases; remaining cases pre-resolved to populate metrics")

tab_overview, tab_queue, tab_detail, tab_copilot, tab_benchmark, tab_audit = st.tabs(
    ["Overview", "Verification Queue", "Case Detail", "Human Co-Pilot", "Benchmark", "Audit History"]
)

with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Applications", len(cases))
    col2.metric("Avg Resolution Time (hrs)", f"{average_resolution_time(cases):.2f}")
    col3.metric("GMV at Risk", f"₹{gmv_at_risk(cases):,.0f}")
    col4.metric("Compliance Overrides", compliance_overrides(cases))

    recovery = recovery_summary(cases)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Recovery Rate", f"{recovery['recovery_rate']:.1%}")
    r2.metric("Auto-Resolved", recovery["automatically_resolved_cases"])
    r3.metric("Human Review", recovery["human_review_cases"])
    r4.metric("Recovered Revenue", f"₹{recovery['estimated_recovered_revenue']:,.0f}")

    df = cases_to_df(cases)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.pie(df, names="Exception Type", title="Applications by Exception Type")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.pie(df, names="Status", title="Applications by Status")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Estimated Revenue Unlocked (synthetic estimate, not actual recovered revenue)")
    total_rev = sum(estimated_revenue(c, resolution_hours(c)) for c in cases if c.resolved_at)
    st.metric("Estimated Revenue Unlocked", f"₹{total_rev:,.0f}")

with tab_queue:
    df = cases_to_df(cases).sort_values("Priority", ascending=False)
    st.dataframe(df, use_container_width=True, height=500)

with tab_detail:
    demo_ids = [c.case_id for c in cases if c.__dict__.get("is_demo_interactive")]
    st.info("Live-interactive demo cases: " + ", ".join(demo_ids))

    case_id = st.selectbox("Select case", [c.case_id for c in cases])
    case = find_case(cases, case_id)

    st.subheader(f"{case.case_id} — {case.merchant.legal_name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Exception Type", case.exception_type.value if case.exception_type else "-")
    c2.metric("Risk Level", case.risk_level.value)
    c3.metric("State", case.state.value)

    st.write("**Recovery Details**")
    st.json({
        "status": case.recovery_status,
        "action": case.recovery_action,
        "attempts": case.recovery_attempts,
        "reason": case.recovery_reason,
        "estimated_recovered_revenue": case.estimated_recovered_revenue,
    })

    st.write("**Submitted Fields**")
    st.json({
        "legal_name": case.merchant.legal_name,
        "trade_name": case.merchant.trade_name,
        "monthly_gmv": case.merchant.monthly_gmv,
    })

    st.write("**Deterministic Rule Results**")
    for r in case.rule_results:
        if not r.passed:
            st.warning(f"{r.rule_name}: {r.detail}  \n_{rule_failure_label(r.rule_name)}_")
        else:
            st.success(f"{r.rule_name}: {r.detail}")

    st.write("**State Transition History**")
    for h in case.history:
        st.text(h)

    if case.exception_type == ExceptionType.SAFE_TO_REMEDIATE and case.document_issues:
        st.subheader("Micro-Remediation Simulator")
        issue = case.document_issues[0]
        st.info(explain_issue(issue))

        if case.state == CaseState.PROCESSING:
            st.warning("This case needs evidence correction before it can proceed. It has not yet been resolved.")

        if st.button("Send Correction Request", key=f"send_{case.case_id}"):
            result = send_correction_request(case)
            log_event("CORRECTION_REQUEST_SENT", case.case_id, result)
            st.success(result["message"])

        doc_id = st.text_input("Replacement document ID", value="DOC-0001", key=f"doc_{case.case_id}")
        if st.button("Upload Replacement", key=f"upload_{case.case_id}"):
            result = upload_replacement(case, doc_id)
            log_event("REPLACEMENT_UPLOADED", case.case_id, result)
            st.success(f"Uploaded {doc_id}")

        if st.button("Re-run Verification", key=f"rerun_{case.case_id}"):
            passed = st.checkbox("Replacement passed verification", value=True, key=f"passed_{case.case_id}")
            result = rerun_verification(case, passed=passed)
            case.recovery_attempts += 1
            if passed:
                case.recovery_status = "recovered"
                case.recovery_action = "verification_passed"
                case.recovery_reason = "Replacement passed verification"
                case.confidence = 1.0
                case.resolved_at = case.created_at + timedelta(minutes=rng.randint(8, 40))
                case.estimated_recovered_revenue = estimated_revenue(case, resolution_hours(case))
            else:
                case.recovery_status = "failed"
                case.recovery_action = "verification_failed"
                case.recovery_reason = "Replacement failed verification"
            log_event("VERIFICATION_RERUN", case.case_id, result)
            st.success(f"Verification result: {result['state']}")

        if case.state == CaseState.APPROVED:
            if st.button("Delete Temporary Document + Unlock Revenue", key=f"delete_{case.case_id}"):
                deletion_event = delete_temporary_document(case, doc_id)
                log_event("DOCUMENT_RETENTION_POLICY_APPLIED", case.case_id, deletion_event)
                unlock_result = unlock_revenue(case)
                log_event("REVENUE_UNLOCKED", case.case_id, unlock_result)
                st.success("Temporary document deleted. Revenue unlocked.")
                st.json(deletion_event)

    if case.exception_type == ExceptionType.AMBIGUOUS_REVIEW and case.state == CaseState.PROCESSING:
        st.warning("This case needs human review before it can proceed. It has not yet been resolved.")
        mismatch = case.__dict__.get("name_mismatch")
        if mismatch:
            st.write(f"Legal name: **{mismatch['legal_name']}**")
            st.write(f"Trade name: **{mismatch['trade_name']}**")
        brief = generate_review_brief(case, mismatch)
        st.info(brief)

        col1, col2, col3 = st.columns(3)
        if col1.button("Approve", key=f"approve_detail_{case.case_id}"):
            case.transition(CaseState.APPROVED, "Human reviewer approved")
            case.confidence = 0.7
            case.recovery_status = "human_review_resolved"
            case.recovery_action = "human_review"
            case.recovery_attempts += 1
            case.recovery_reason = "Human reviewer approved the ambiguous case"
            case.resolved_at = case.created_at
            log_event("HUMAN_DECISION", case.case_id, {"decision": "APPROVED"})
            st.success("Approved by human reviewer")
        if col2.button("Request Evidence", key=f"evidence_detail_{case.case_id}"):
            case.transition(CaseState.NEEDS_EVIDENCE, "Human reviewer requested more evidence")
            case.recovery_status = "awaiting_evidence"
            case.recovery_action = "request_evidence"
            case.recovery_attempts += 1
            case.recovery_reason = "Human reviewer requested additional evidence"
            log_event("HUMAN_DECISION", case.case_id, {"decision": "REQUEST_EVIDENCE"})
            st.info("Evidence requested")
        if col3.button("Escalate", key=f"escalate_detail_{case.case_id}"):
            case.transition(CaseState.ESCALATED, "Human reviewer escalated")
            case.recovery_status = "human_review"
            case.recovery_action = "escalate_review"
            case.recovery_attempts += 1
            case.recovery_reason = "Human reviewer escalated the ambiguous case"
            log_event("HUMAN_DECISION", case.case_id, {"decision": "ESCALATED"})
            st.warning("Escalated")

    if case.exception_type == ExceptionType.HARD_COMPLIANCE_BLOCK:
        st.error(f"Hard compliance signal detected: {case.__dict__.get('hard_issue', 'unspecified')}. Cannot be auto-approved or auto-rejected by AI.")
        if case.state not in (CaseState.ESCALATED, CaseState.REJECTED):
            st.warning("This case is awaiting compliance escalation. It has not yet been resolved.")
            if st.button("Escalate to Compliance Team", key=f"escalate_hard_{case.case_id}"):
                case.transition(CaseState.ESCALATED, "Escalated to compliance team for manual review")
                log_event("HUMAN_DECISION", case.case_id, {"decision": "ESCALATED", "reason": case.__dict__.get("hard_issue")})
                st.warning("Escalated. Awaiting compliance team decision — AI has no authority to resolve this case.")
        else:
            st.success(f"Resolved: {case.state.value}")

with tab_copilot:
    ambiguous_cases = [c for c in cases if c.exception_type == ExceptionType.AMBIGUOUS_REVIEW and c.__dict__.get("is_demo_interactive")]
    resolved_ambiguous = [c for c in cases if c.exception_type == ExceptionType.AMBIGUOUS_REVIEW and not c.__dict__.get("is_demo_interactive")]
    st.write(f"{len(ambiguous_cases)} cases pending live human review, {len(resolved_ambiguous)} already resolved (simulated)")

    for c in ambiguous_cases:
        with st.expander(f"{c.case_id} — {c.merchant.legal_name}"):
            mismatch = c.__dict__.get("name_mismatch")
            if mismatch:
                st.write(f"Legal name: **{mismatch['legal_name']}**")
                st.write(f"Trade name: **{mismatch['trade_name']}**")

            brief = generate_review_brief(c, mismatch)
            st.info(brief)

            col1, col2, col3 = st.columns(3)
            if col1.button("Approve", key=f"approve_{c.case_id}"):
                c.transition(CaseState.APPROVED, "Human reviewer approved")
                c.confidence = 0.7
                c.resolved_at = c.created_at
                log_event("HUMAN_DECISION", c.case_id, {"decision": "APPROVED"})
                st.success("Approved by human reviewer")
            if col2.button("Request Evidence", key=f"evidence_{c.case_id}"):
                c.transition(CaseState.NEEDS_EVIDENCE, "Human reviewer requested more evidence")
                log_event("HUMAN_DECISION", c.case_id, {"decision": "REQUEST_EVIDENCE"})
                st.info("Evidence requested")
            if col3.button("Escalate", key=f"escalate_{c.case_id}"):
                c.transition(CaseState.ESCALATED, "Human reviewer escalated")
                log_event("HUMAN_DECISION", c.case_id, {"decision": "ESCALATED"})
                st.warning("Escalated")

with tab_benchmark:
    summary = benchmark_summary(cases)
    col1, col2 = st.columns(2)
    col1.metric("FIFO Baseline Avg (hrs)", f"{summary['fifo_baseline_avg_hours']:.1f}")
    col2.metric("LedgerGate Avg (hrs)", f"{summary['LedgerGate_avg_hours']:.2f}")

    col3, col4, col5 = st.columns(3)
    col3.metric("GMV at Risk", f"₹{summary['gmv_at_risk']:,.0f}")
    col4.metric("Estimated Revenue Unlocked", f"₹{summary['estimated_revenue_unlocked']:,.0f}")
    col5.metric("Compliance Overrides", summary["compliance_overrides"])

    st.subheader("Recovery Performance")
    recovery = recovery_summary(cases)
    st.json(recovery)

    st.caption("FIFO baseline and LedgerGate figures reflect the synthetic dataset in this demo, not production Razorpay metrics.")

with tab_audit:
    filter_case = st.text_input("Filter by case ID (optional)")
    entries = read_audit_log(filter_case if filter_case else None)
    st.write(f"{len(entries)} audit events")
    for e in entries[-100:]:
        st.json(e)