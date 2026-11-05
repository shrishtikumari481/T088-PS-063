from datetime import datetime, timedelta


RESERVATION_HOURS = 72


def create_reservation(unit_id, request_id, reservation_ts):
    """
    Creates a 72-hour reservation for a PRBC unit.
    """

    reservation_time = datetime.strptime(
        reservation_ts, "%Y-%m-%d %H:%M:%S"
    )

    expiry_time = reservation_time + timedelta(
        hours=RESERVATION_HOURS
    )

    return {
        "unit_id": unit_id,
        "request_id": request_id,
        "reservation_state": "CROSSMATCHED",
        "reservation_ts": reservation_ts,
        "release_ts": expiry_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

def check_reservation_status(reservation, current_ts):
    """
    Checks whether a reservation has reached its 72-hour limit.

    Automatically releases unused reservations.
    """

    current_time = datetime.strptime(
        current_ts, "%Y-%m-%d %H:%M:%S"
    )

    release_time = datetime.strptime(
        reservation["release_ts"], "%Y-%m-%d %H:%M:%S"
    )

    if reservation["reservation_state"] == "ISSUED":
        return "ISSUED"

    if current_time >= release_time:
        return "AVAILABLE"

    return "CROSSMATCHED"

def emergency_uncrossmatched_issue(
    patient_group,
    patient_rh,
    compatible_unit_id=None
):
    """
    Handles emergency blood issue without waiting
    for cross-match.
    """

    if not patient_group or not patient_rh:
        return {
            "unit_id": "O-",
            "status": "ISSUED",
            "crossmatch_state": "PENDING_RETROSPECTIVE"
        }

    if not compatible_unit_id:
        return None

    return {
        "unit_id": compatible_unit_id,
        "status": "ISSUED",
        "crossmatch_state": "PENDING_RETROSPECTIVE"
    }


def check_retrospective_crossmatch(issue_ts, current_ts, result):
    """
    Checks whether retrospective cross-match
    is completed within 24 hours.
    """

    issue_time = datetime.strptime(
        issue_ts, "%Y-%m-%d %H:%M:%S"
    )

    current_time = datetime.strptime(
        current_ts, "%Y-%m-%d %H:%M:%S"
    )

    elapsed = current_time - issue_time

    if result in ["COMPATIBLE", "INCOMPATIBLE"]:
        return "COMPLETED"

    if elapsed > timedelta(hours=24):
        return "FLAGGED"

    return "PENDING"