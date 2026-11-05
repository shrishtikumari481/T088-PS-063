from datetime import datetime, timedelta


SLA_LIMITS = {
    "EMERGENCY": 15,
    "URGENT": 120,
    "ROUTINE": 1440
}


def calculate_sla_deadline(request_ts, urgency):
    """
    Calculates the maximum allocation deadline.

    Emergency: 15 minutes
    Urgent: 2 hours
    Routine: 24 hours
    """

    request_time = datetime.strptime(
        request_ts, "%Y-%m-%d %H:%M:%S"
    )

    urgency = urgency.upper()

    if urgency not in SLA_LIMITS:
        raise ValueError("Invalid urgency level")

    allowed_minutes = SLA_LIMITS[urgency]

    deadline = request_time + timedelta(
        minutes=allowed_minutes
    )

    return deadline.strftime("%Y-%m-%d %H:%M:%S")


def calculate_partial_allocation(requested_units, available_units):
    """
    Calculates allocated units and remaining shortfall.
    """

    if requested_units <= 0 or available_units < 0:
        raise ValueError("Invalid unit count")

    allocated_units = min(requested_units, available_units)

    shortfall = requested_units - allocated_units

    if shortfall == 0:
        status = "FULFILLED"
    elif allocated_units > 0:
        status = "PARTIAL"
    else:
        status = "PENDING"

    return {
        "allocated_units": allocated_units,
        "shortfall": shortfall,
        "status": status
    }


def prioritize_shortage_queue(requests):
    """
    Sorts pending requests by urgency and request time.
    Emergency gets highest priority.
    Older requests come first when urgency is equal.
    """

    priority = {
        "EMERGENCY": 1,
        "URGENT": 2,
        "ROUTINE": 3
    }

    return sorted(
        requests,
        key=lambda request: (
            priority[request["urgency"].upper()],
            request["request_ts"]
        )
    )


def retry_shortage_requests(requests, newly_available_units):
    """
    Retries pending requests when new stock becomes available.
    Requests are processed according to queue priority.
    """

    sorted_requests = prioritize_shortage_queue(requests)

    results = []

    for request in sorted_requests:
        requested_units = request["shortfall"]

        allocation = calculate_partial_allocation(
            requested_units,
            newly_available_units
        )

        newly_available_units -= allocation["allocated_units"]

        results.append({
            "request_id": request["request_id"],
            "allocated_units": allocation["allocated_units"],
            "shortfall": allocation["shortfall"],
            "status": allocation["status"]
        })

    return results