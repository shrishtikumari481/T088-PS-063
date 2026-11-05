def reserve_unit(unit_id, request_id, reservations, urgency="ROUTINE"):
    """
    Reserves a blood unit without allowing double reservations.
    """

    for reservation in reservations:
        if (
            reservation["unit_id"] == unit_id
            and reservation["reservation_state"] == "CROSSMATCHED"
        ):
            return False

    reservations.append({
        "unit_id": unit_id,
        "request_id": request_id,
        "urgency": urgency.upper(),
        "reservation_state": "CROSSMATCHED"
    })

    return True


def preempt_routine_reservation(
    unit_id, emergency_request_id, reservations, waiting_queue
):
    """
    Transfers a routine reservation to an emergency request.

    The routine request is added back to the waiting queue.
    """

    for reservation in reservations:

        if (
            reservation["unit_id"] == unit_id
            and reservation["reservation_state"] == "CROSSMATCHED"
        ):

            if reservation["urgency"] != "ROUTINE":
                return False

            # Release the routine reservation
            reservation["reservation_state"] = "PREEMPTED"

            # Return the routine request to the waiting queue
            waiting_queue.append(reservation["request_id"])

            # Give the unit to the emergency request
            return reserve_unit(
                unit_id,
                emergency_request_id,
                reservations,
                "EMERGENCY"
            )

    return False