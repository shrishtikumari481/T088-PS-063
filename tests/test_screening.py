from datetime import datetime, timedelta

from src.screening import evaluate_screening


def make_results():
    return [
        {"marker": "HIV", "result": "NON_REACTIVE"},
        {"marker": "HBV", "result": "NON_REACTIVE"},
        {"marker": "HCV", "result": "NON_REACTIVE"},
        {"marker": "SYPHILIS", "result": "NON_REACTIVE"},
        {"marker": "MALARIA", "result": "NON_REACTIVE"},
    ]


def test_all_markers_non_reactive():
    collection = datetime(2026, 1, 1, 10, 0)
    current = datetime(2026, 1, 2, 10, 0)

    result = evaluate_screening(
        collection, make_results(), "PRBC", current
    )

    assert result == (
        "AVAILABLE", False, "BR-03: SCREENING_CLEARED"
    )


def test_one_marker_reactive():
    collection = datetime(2026, 1, 1, 10, 0)
    current = datetime(2026, 1, 2, 10, 0)

    results = make_results()
    results[1]["result"] = "REACTIVE"

    result = evaluate_screening(
        collection, results, "PRBC", current
    )

    assert result[0] == "DISCARDED"
    assert result[1] is True


def test_missing_results_within_72_hours():
    collection = datetime(2026, 1, 1, 10, 0)
    current = collection + timedelta(hours=48)

    result = evaluate_screening(
        collection, [], "PRBC", current
    )

    assert result[0] == "QUARANTINE"


def test_prbc_quarantined_after_72_hours():
    collection = datetime(2026, 1, 1, 10, 0)
    current = collection + timedelta(hours=80)

    result = evaluate_screening(
        collection, [], "PRBC", current
    )

    assert result[0] == "QUARANTINE"


def test_platelet_discarded_after_72_hours():
    collection = datetime(2026, 1, 1, 10, 0)
    current = collection + timedelta(hours=80)

    result = evaluate_screening(
        collection, [], "PLATELET", current
    )

    assert result[0] == "DISCARDED"