from core.rules import (
    check_pan_format,
    check_gstin_format,
    check_gstin_active,
    check_gstin_pan_link,
    check_bank_name_match,
    check_legal_trade_name_equivalence,
    check_restricted_signal,
    check_duplicate,
    run_all_rules,
)


def test_pan_format_valid():
    r = check_pan_format("ABCDE1234F")
    assert r.passed is True


def test_pan_format_invalid():
    r = check_pan_format("12345ABCDE")
    assert r.passed is False


def test_gstin_format_valid():
    r = check_gstin_format("27ABCDE1234F1Z5")
    assert r.passed is True


def test_gstin_format_invalid():
    r = check_gstin_format("BADGSTIN")
    assert r.passed is False


def test_gstin_active():
    assert check_gstin_active(True).passed is True
    assert check_gstin_active(False).passed is False


def test_gstin_pan_link_match():
    r = check_gstin_pan_link("27ABCDE1234F1Z5", "ABCDE1234F")
    assert r.passed is True


def test_gstin_pan_link_mismatch():
    r = check_gstin_pan_link("27XXXXX9999X1Z5", "ABCDE1234F")
    assert r.passed is False


def test_bank_name_match_identical():
    r = check_bank_name_match("Test Co", "Test Co")
    assert r.passed is True


def test_bank_name_match_dissimilar():
    r = check_bank_name_match("Test Co", "Completely Different Name LLC")
    assert r.passed is False


def test_legal_trade_name_equivalence_close():
    r = check_legal_trade_name_equivalence("ABC Enterprises", "ABC Enterprise Pvt Ltd")
    assert r.passed is True


def test_legal_trade_name_equivalence_far():
    r = check_legal_trade_name_equivalence("S.K. Tech", "Satish Kumar Technologies")
    assert r.passed is False


def test_restricted_signal_clear():
    r = check_restricted_signal(False)
    assert r.passed is True


def test_restricted_signal_flagged():
    r = check_restricted_signal(True)
    assert r.passed is False


def test_duplicate_detection():
    seen = {"ABCDE1234F"}
    r1 = check_duplicate("ABCDE1234F", seen)
    r2 = check_duplicate("ZZZZZ9999Z", seen)
    assert r1.passed is False
    assert r2.passed is True


def test_run_all_rules_returns_eight_results():
    case = {
        "merchant": {
            "pan": "ABCDE1234F",
            "gstin": "27ABCDE1234F1Z5",
            "legal_name": "Test Co",
            "trade_name": "Test Co",
            "bank_account_name": "Test Co",
        },
        "gstin_active": True,
        "restricted_flag": False,
    }
    results = run_all_rules(case, set())
    assert len(results) == 8
    assert all(r.passed for r in results)