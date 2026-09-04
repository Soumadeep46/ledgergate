from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ExceptionType(str, Enum):
    SAFE_TO_REMEDIATE = "SAFE_TO_REMEDIATE"
    AMBIGUOUS_REVIEW = "AMBIGUOUS_REVIEW"
    HARD_COMPLIANCE_BLOCK = "HARD_COMPLIANCE_BLOCK"
    CLEAN_APPROVAL = "CLEAN_APPROVAL"


class CaseState(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    REVALIDATING = "REVALIDATING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    REVENUE_UNLOCKED = "REVENUE_UNLOCKED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class DocumentIssue:
    doc_type: str
    issue: str
    detail: str


@dataclass
class RuleResult:
    rule_name: str
    passed: bool
    detail: str


@dataclass
class Merchant:
    merchant_id: str
    legal_name: str
    trade_name: str
    pan: str
    gstin: str
    bank_account_name: str
    monthly_gmv: float


@dataclass
class Case:
    case_id: str
    merchant: Merchant
    cohort: str  # "SAFE", "AMBIGUOUS", "HARD"
    document_issues: list[DocumentIssue] = field(default_factory=list)
    rule_results: list[RuleResult] = field(default_factory=list)
    exception_type: Optional[ExceptionType] = None
    risk_level: RiskLevel = RiskLevel.LOW
    state: CaseState = CaseState.RECEIVED
    confidence: float = 0.0
    baseline_hours: float = 48.0
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    history: list[str] = field(default_factory=list)
    recovery_status: str = "not_started"
    recovery_action: str = ""
    recovery_attempts: int = 0
    recovery_reason: str = ""
    estimated_recovered_revenue: float = 0.0

    def transition(self, new_state: CaseState, note: str = ""):
        self.history.append(
            f"{datetime.utcnow().isoformat()} | {self.state.value} -> {new_state.value} | {note}"
        )
        self.state = new_state