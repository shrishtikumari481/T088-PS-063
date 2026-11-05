from src.blood_compatibility import check_emergency_rh_exception, check_ffp_compatibility, check_prbc_compatibility


def test_o_negative_patient():
    assert check_prbc_compatibility("O", "NEG", "O", "NEG") is True
    assert check_prbc_compatibility("A", "NEG", "O", "NEG") is False


def test_a_positive_patient():
    assert check_prbc_compatibility("O", "NEG", "A", "POS") is True
    assert check_prbc_compatibility("A", "POS", "A", "POS") is True
    assert check_prbc_compatibility("B", "POS", "A", "POS") is False


def test_ab_positive_patient():
    assert check_prbc_compatibility("O", "NEG", "AB", "POS") is True
    assert check_prbc_compatibility("A", "POS", "AB", "POS") is True
    assert check_prbc_compatibility("B", "NEG", "AB", "POS") is True
    assert check_prbc_compatibility("AB", "POS", "AB", "POS") is True


def test_rh_negative_patient():
    assert check_prbc_compatibility("O", "NEG", "A", "NEG") is True
    assert check_prbc_compatibility("A", "POS", "A", "NEG") is False


def test_rh_positive_patient():
    assert check_prbc_compatibility("A", "NEG", "A", "POS") is True
    assert check_prbc_compatibility("A", "POS", "A", "POS") is True


    from src.blood_compatibility import check_emergency_rh_exception


def test_emergency_male_can_receive_rh_positive():
    assert check_emergency_rh_exception(
        "POS", "NEG", "M", 25, "EMERGENCY", 0
    ) is True


def test_emergency_female_above_50_can_receive_rh_positive():
    assert check_emergency_rh_exception(
        "POS", "NEG", "F", 51, "EMERGENCY", 0
    ) is True


def test_emergency_female_exactly_50_cannot_receive_rh_positive():
    assert check_emergency_rh_exception(
        "POS", "NEG", "F", 50, "EMERGENCY", 0
    ) is False


def test_rh_negative_stock_available():
    assert check_emergency_rh_exception(
        "POS", "NEG", "M", 25, "EMERGENCY", 2
    ) is False


def test_routine_request_cannot_use_exception():
    assert check_emergency_rh_exception(
        "POS", "NEG", "M", 25, "ROUTINE", 0
    ) is False


    from src.blood_compatibility import check_ffp_compatibility


def test_o_patient_receives_ffp_from_all_groups():
    assert check_ffp_compatibility("O", "O") is True
    assert check_ffp_compatibility("A", "O") is True
    assert check_ffp_compatibility("B", "O") is True
    assert check_ffp_compatibility("AB", "O") is True


def test_a_patient_receives_ffp():
    assert check_ffp_compatibility("A", "A") is True
    assert check_ffp_compatibility("AB", "A") is True
    assert check_ffp_compatibility("O", "A") is False


def test_b_patient_receives_ffp():
    assert check_ffp_compatibility("B", "B") is True
    assert check_ffp_compatibility("AB", "B") is True
    assert check_ffp_compatibility("A", "B") is False


def test_ab_patient_receives_ffp_only_from_ab():
    assert check_ffp_compatibility("AB", "AB") is True
    assert check_ffp_compatibility("O", "AB") is False
    assert check_ffp_compatibility("A", "AB") is False
    assert check_ffp_compatibility("B", "AB") is False