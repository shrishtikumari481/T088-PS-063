from src.billing import calculate_invoice, evaluate_return


# BILLING TESTS

def test_prbc_private_normal():
    result = calculate_invoice("PRBC", "PRIVATE", "ROUTINE")
    assert result["amount"] == 1550


def test_prbc_government_discount():
    result = calculate_invoice("PRBC", "GOVERNMENT", "ROUTINE")
    assert result["government_discount"] == 775
    assert result["amount"] == 775


def test_emergency_surcharge():
    result = calculate_invoice("FFP", "PRIVATE", "EMERGENCY")
    assert result["emergency_surcharge"] == 500
    assert result["amount"] == 900


def test_government_emergency_invoice():
    result = calculate_invoice("PRBC", "GOVERNMENT", "EMERGENCY")
    assert result["amount"] == 1275


def test_invalid_component():
    try:
        calculate_invoice("WHOLE_BLOOD", "PRIVATE", "ROUTINE")
    except ValueError:
        assert True
    else:
        assert False


# RETURN TESTS

def test_return_within_30_minutes():
    result = evaluate_return(
        "2026-11-05 10:00:00",
        "2026-11-05 10:20:00",
        True
    )
    assert result["status"] == "RETURNED"
    assert result["billable"] is False


def test_return_exactly_30_minutes():
    result = evaluate_return(
        "2026-11-05 10:00:00",
        "2026-11-05 10:30:00",
        True
    )
    assert result["status"] == "RETURNED"


def test_return_after_30_minutes():
    result = evaluate_return(
        "2026-11-05 10:00:00",
        "2026-11-05 10:40:00",
        True
    )
    assert result["status"] == "DISCARDED"
    assert result["billable"] is True


def test_return_without_cold_chain():
    result = evaluate_return(
        "2026-11-05 10:00:00",
        "2026-11-05 10:10:00",
        False
    )
    assert result["status"] == "DISCARDED"
    assert result["billable"] is True
