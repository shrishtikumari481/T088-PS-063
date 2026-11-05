from src.allocation import select_best_blood_group, select_fefo_unit


def test_identical_group_gets_first_priority():
    stock = {
        "A+": 2,
        "O+": 8,
        "A-": 5
    }

    result = select_best_blood_group("A", "POS", stock)

    assert result == "A+"


def test_largest_compatible_stock_is_selected():
    stock = {
        "O+": 8,
        "A-": 5,
        "O-": 10
    }

    result = select_best_blood_group("A", "POS", stock)

    assert result == "O+"


def test_o_negative_is_reserved_for_routine_requests():
    stock = {
        "O-": 5
    }

    result = select_best_blood_group(
        "A", "POS", stock, emergency=False
    )

    assert result == "O-"


def test_o_negative_can_be_used_in_emergency():
    stock = {
        "O-": 5
    }

    result = select_best_blood_group(
        "A", "POS", stock, emergency=True
    )

    assert result == "O-"


def test_no_compatible_stock_returns_none():
    stock = {
        "B-": 5
    }

    result = select_best_blood_group("A", "NEG", stock)

    assert result is None



    from src.allocation import select_fefo_unit


def test_fefo_selects_earliest_expiring_unit():
    units = [
        {"unit_id": "U001", "expiry_date": "2026-11-10 23:59:00"},
        {"unit_id": "U002", "expiry_date": "2026-11-07 23:59:00"},
        {"unit_id": "U003", "expiry_date": "2026-11-15 23:59:00"}
    ]

    result = select_fefo_unit(units)

    assert result["unit_id"] == "U002"


def test_fefo_returns_none_for_empty_stock():
    result = select_fefo_unit([])

    assert result is None


def test_fefo_selects_only_available_unit():
    units = [
        {"unit_id": "U005", "expiry_date": "2026-11-12 23:59:00"}
    ]

    result = select_fefo_unit(units)

    assert result["unit_id"] == "U005"