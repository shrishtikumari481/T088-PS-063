from src.allocation import select_best_blood_group, select_fefo_unit
from src.allocation import allocate_blood_unit

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
        {
            "unit_id": "U005",
            "expiry_date": "2026-11-12 23:59:00"
        }
    ]

    result = select_fefo_unit(units)

    assert result["unit_id"] == "U005"
    units = [
        {"unit_id": "U005", "expiry_date": "2026-11-12 23:59:00"}
    ]

    result = select_fefo_unit(units)

    assert result["unit_id"] == "U005"


def test_complete_allocation_selects_identical_group_and_fefo():
        units_by_group = {
            "A+": [
               {"unit_id": "U001", "expiry_date": "2026-11-10 23:59:00"},
               {"unit_id": "U002", "expiry_date": "2026-11-07 23:59:00"}
            ],
            "O+": [
               {"unit_id": "U003", "expiry_date": "2026-11-06 23:59:00"}
            ]
        }

        result = allocate_blood_unit(
            "A", "POS", units_by_group
        )

        assert result["blood_group"] == "A+"
        assert result["unit"]["unit_id"] == "U002"


def test_complete_allocation_selects_largest_stock_group():
    units_by_group = {
        "O+": [
            {"unit_id": "U001", "expiry_date": "2026-11-10 23:59:00"},
            {"unit_id": "U002", "expiry_date": "2026-11-07 23:59:00"},
            {"unit_id": "U003", "expiry_date": "2026-11-12 23:59:00"}
        ],
        "A-": [
            {"unit_id": "U004", "expiry_date": "2026-11-06 23:59:00"}
        ]
    }

    result = allocate_blood_unit(
        "A", "POS", units_by_group
    )

    assert result["blood_group"] == "O+"
    assert result["unit"]["unit_id"] == "U002"


def test_complete_allocation_returns_none_without_stock():
    result = allocate_blood_unit(
        "A", "POS", {}
    )

    assert result is None


def test_emergency_rh_exception_for_male():
    units_by_group = {
        "A+": [
            {
                "unit_id": "U101",
                "expiry_date": "2026-11-07 23:59:00"
            }
        ]
    }

    result = allocate_blood_unit(
        "A",
        "NEG",
        units_by_group,
        emergency=True,
        patient_gender="M",
        patient_age=30
    )

    assert result is not None
    assert result["blood_group"] == "A+"


def test_emergency_rh_exception_for_female_over_50():
    units_by_group = {
        "A+": [
            {
                "unit_id": "U102",
                "expiry_date": "2026-11-07 23:59:00"
            }
        ]
    }

    result = allocate_blood_unit(
        "A",
        "NEG",
        units_by_group,
        emergency=True,
        patient_gender="F",
        patient_age=51
    )

    assert result is not None


def test_female_exactly_50_cannot_receive_rh_positive():
    units_by_group = {
        "A+": [
            {
                "unit_id": "U103",
                "expiry_date": "2026-11-07 23:59:00"
            }
        ]
    }

    result = allocate_blood_unit(
        "A",
        "NEG",
        units_by_group,
        emergency=True,
        patient_gender="F",
        patient_age=50
    )

    assert result is None