from src.crossmatch import create_reservation


def reserve_unit(
    unit_id,
    request_id,
    reservations,
    urgency="ROUTINE",
    reservation_ts=None
):
    """
    Reserve a unit without allowing double reservations.
    """

    for reservation in reservations:
        if (
            reservation["unit_id"] == unit_id
            and reservation["reservation_state"] == "CROSSMATCHED"
        ):
            return False

    if reservation_ts:
        reservation = create_reservation(
            unit_id,
            request_id,
            reservation_ts,
            urgency
        )
    else:
        reservation = {
            "unit_id": unit_id,
            "request_id": request_id,
            "urgency": urgency.upper(),
            "reservation_state": "CROSSMATCHED"
        }

    reservations.append(reservation)

    return True


def preempt_routine_reservation(
    unit_id,
    emergency_request_id,
    reservations,
    waiting_queue,
    emergency_ts=None,
    waiting_entry=None
):
    """
    Transfer a routine reservation to an emergency request.
    """

    for reservation in reservations:

        if (
            reservation["unit_id"] == unit_id
            and reservation["reservation_state"] == "CROSSMATCHED"
        ):

            if reservation.get("urgency") != "ROUTINE":
                return False

            # Release the routine reservation.
            reservation["reservation_state"] = "PREEMPTED"

            # Return the routine request to the waiting queue.
            if waiting_entry is not None:
                waiting_queue.append(waiting_entry)
            else:
                waiting_queue.append(reservation["request_id"])

            # Reserve the same unit for the emergency request.
            return reserve_unit(
                unit_id,
                emergency_request_id,
                reservations,
                "EMERGENCY",
                emergency_ts
            )

    return False