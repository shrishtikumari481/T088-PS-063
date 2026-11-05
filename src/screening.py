from datetime import datetime, timedelta


REQUIRED_MARKERS = {
    "HIV",
    "HBV",
    "HCV",
    "SYPHILIS",
    "MALARIA"
}


def evaluate_screening(collection_ts, results, component, current_ts):
    """
    Evaluates screening results for a blood donation.

    Returns:
        unit_status, donor_permanently_deferred, reason
    """

    # Convert screening results into a marker-result dictionary
    screening = {
        result["marker"]: result["result"]
        for result in results
    }

    # Rule 1: Any reactive marker means discard all components
    if "REACTIVE" in screening.values():
        return (
            "DISCARDED",
            True,
            "BR-03: REACTIVE_SCREENING"
        )

    # Rule 2: Check whether all five markers are available
    all_results_received = (
        REQUIRED_MARKERS.issubset(screening.keys())
    )

    # Rule 3: All five markers must be NON_REACTIVE
    if all_results_received:
        all_non_reactive = all(
            screening[marker] == "NON_REACTIVE"
            for marker in REQUIRED_MARKERS
        )

        if all_non_reactive:
            return (
                "AVAILABLE",
                False,
                "BR-03: SCREENING_CLEARED"
            )

    # Rule 4: Check whether 72 hours have passed
    elapsed_time = current_ts - collection_ts

    if elapsed_time > timedelta(hours=72):

        # Platelets are discarded after 72 hours without results
        if component == "PLATELET":
            return (
                "DISCARDED",
                False,
                "BR-03: PLATELET_SCREENING_TIMEOUT"
            )

    # Other components remain quarantined
    return (
        "QUARANTINE",
        False,
        "BR-03: SCREENING_PENDING"
    )