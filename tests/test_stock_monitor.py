from src.stock_monitor import check_stock_alert


def test_critical_stock():
    assert check_stock_alert(1, "A+") == "CRITICAL"


def test_o_negative_shortage():
    assert check_stock_alert(6, "O-") == "SHORTAGE"


def test_normal_blood_group_shortage():
    assert check_stock_alert(3, "A+") == "SHORTAGE"


def test_sufficient_stock():
    assert check_stock_alert(8, "A+") == ""


def test_o_negative_sufficient_stock():
    assert check_stock_alert(8, "O-") == ""


def test_negative_stock_is_invalid():
    try:
        check_stock_alert(-1, "A+")
    except ValueError:
        assert True
    else:
        assert False