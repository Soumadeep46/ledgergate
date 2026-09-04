from __future__ import annotations
import re
from difflib import SequenceMatcher
from core.models import RuleResult

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}$")

NAME_MATCH_THRESHOLD = 0.55  # below this -> ambiguous


def check_pan_format(pan: str) -> RuleResult:
    ok = bool(PAN_PATTERN.match(pan))
    return RuleResult("PAN_FORMAT", ok, "PAN format valid" if ok else f"PAN '{pan}' fails format check")


def check_gstin_format(gstin: str) -> RuleResult:
    ok = bool(GSTIN_PATTERN.match(gstin))
    return RuleResult("GSTIN_FORMAT", ok, "GSTIN format valid" if ok else f"GSTIN '{gstin}' fails format check")


def check_gstin_active(gstin_active: bool) -> RuleResult:
    return RuleResult(
        "GSTIN_STATUS",
        gstin_active,
        "GSTIN active" if gstin_active else "GSTIN inactive — hard compliance signal",
    )


def check_gstin_pan_link(gstin: str, pan: str) -> RuleResult:
    # GSTIN embeds PAN at positions 2:12
    ok = len(gstin) >= 12 and gstin[2:12] == pan
    return RuleResult(
        "GSTIN_PAN_LINK",
        ok,
        "GSTIN-PAN linkage consistent" if ok else "GSTIN does not embed matching PAN",
    )


def check_bank_name_match(legal_name: str, bank_account_name: str) -> RuleResult:
    score = SequenceMatcher(None, legal_name.lower(), bank_account_name.lower()).ratio()
    ok = score >= NAME_MATCH_THRESHOLD
    return RuleResult(
        "BANK_NAME_MATCH",
        ok,
        f"Bank account name similarity {score:.2f}" + ("" if ok else " — below threshold"),
    )


def check_legal_trade_name_equivalence(legal_name: str, trade_name: str) -> RuleResult:
    score = SequenceMatcher(None, legal_name.lower(), trade_name.lower()).ratio()
    ok = score >= NAME_MATCH_THRESHOLD
    return RuleResult(
        "LEGAL_TRADE_NAME_MATCH",
        ok,
        f"Legal/trade name similarity {score:.2f}" + ("" if ok else " — needs review"),
    )


def check_restricted_signal(restricted_flag: bool) -> RuleResult:
    return RuleResult(
        "RESTRICTED_ENTITY_SCREEN",
        not restricted_flag,
        "No restricted-entity match" if not restricted_flag else "Restricted-entity match found — hard block",
    )


def check_duplicate(pan: str, seen_pans: set[str]) -> RuleResult:
    is_dup = pan in seen_pans
    return RuleResult(
        "DUPLICATE_APPLICATION",
        not is_dup,
        "No duplicate PAN found" if not is_dup else f"Duplicate application for PAN '{pan}'",
    )


def run_all_rules(case_dict: dict, seen_pans: set[str]) -> list[RuleResult]:
    m = case_dict["merchant"]
    results = [
        check_pan_format(m["pan"]),
        check_gstin_format(m["gstin"]),
        check_gstin_active(case_dict.get("gstin_active", True)),
        check_gstin_pan_link(m["gstin"], m["pan"]),
        check_bank_name_match(m["legal_name"], m["bank_account_name"]),
        check_legal_trade_name_equivalence(m["legal_name"], m["trade_name"]),
        check_restricted_signal(case_dict.get("restricted_flag", False)),
        check_duplicate(m["pan"], seen_pans),
    ]
    return results