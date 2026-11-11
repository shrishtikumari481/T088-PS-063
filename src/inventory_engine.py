import csv
from src.request_sla import calculate_sla_deadline
from pathlib import Path
from datetime import datetime, timedelta
from unittest import result
from unittest import result
from urllib import request
from urllib import request

from src import allocation

from src.component_expiry import calculate_expiry
from src.screening import evaluate_screening
from src.blood_compatibility import (
    check_prbc_compatibility,
    check_ffp_compatibility,
    check_emergency_rh_exception
)
from src.allocation import allocate_blood_unit
from src.crossmatch import (
    create_reservation,
    check_reservation_status,
    emergency_uncrossmatched_issue,
    check_retrospective_crossmatch
)
from src.request_sla import (
    calculate_sla_deadline,
    calculate_partial_allocation,
    prioritize_shortage_queue
)
from src.hospital_quota import (
    check_daily_quota,
    calculate_replacement_ratio,
    calculate_adjusted_quota
)
from src.stock_monitor import check_stock_alert
from src.billing import calculate_invoice, evaluate_return
from src.reservation_manager import (
    reserve_unit,
    preempt_routine_reservation
)
from src.platelet_pooling import create_platelet_pool


# Project folders
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


# Required output CSV structures
OUTPUT_FIELDS = {

    "unit_status.csv": [
        "unit_id",
        "ts",
        "status",
        "reason"
    ],

    "donation_eligibility.csv": [
        "donation_id",
        "donor_id",
        "decision",
        "failed_rule"
    ],

    "allocations.csv": [
        "request_id",
        "unit_id",
        "unit_group",
        "unit_rh",
        "compatibility_path",
        "reservation_state",
        "allocated_ts",
        "sla_met",
        "note"
    ],

    "stock_positions.csv": [
        "date",
        "blood_group",
        "rh",
        "component",
        "available",
        "quarantine",
        "crossmatched",
        "alert"
    ],

    "invoices.csv": [
        "hospital_id",
        "request_id",
        "unit_id",
        "component",
        "base_charge",
        "government_discount",
        "emergency_surcharge",
        "amount"
    ]
}


# Timestamp format used throughout the project
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class InventoryEngine:

    def __init__(self, data):

        # Store all input data
        self.data = data

        # Create quick lookup dictionaries
        self.donors = {
            donor["donor_id"]: donor
            for donor in data["donors"]
        }

        self.donations = {
            donation["donation_id"]: donation
            for donation in data["donations"]
        }

        self.hospitals = {
            hospital["hospital_id"]: hospital
            for hospital in data["hospitals"]
        }

        self.requests = {
            request["request_id"]: request
            for request in data["requests"]
        }

        self.request_status = {}

        # Store blood components
        self.components = {
            component["unit_id"]: component
            for component in data["components"]
        }

        # Store screening results by donation
        self.screening_results = {}

        for result in data["screening_results"]:

            donation_id = result["donation_id"]

            if donation_id not in self.screening_results:
                self.screening_results[donation_id] = []

            self.screening_results[donation_id].append(result)

        # Initial status of every blood unit
        self.unit_status = {}

        # Store allocation records
        self.allocations = []

        # Store invoice records
        self.invoices = []

        # Store cross-match reservations
        self.reservations = []

        # Store pending requests
        self.shortage_queue = []

        # Store generated reports
        self.output_records = {
            "unit_status.csv": [],
            "donation_eligibility.csv": [],
            "allocations.csv": [],
            "stock_positions.csv": [],
            "invoices.csv": []
        }

        print("Inventory Engine initialized successfully!")
        print("Total donors:", len(self.donors))
        print("Total donations:", len(self.donations))
        print("Total blood units:", len(self.components))
        print("Total hospital requests:", len(self.requests))


    def process_donation(self, donation_id, current_ts):

        # Find the donation
        donation = self.donations.get(donation_id)

        if donation is None:
            print("Donation not found:", donation_id)
            return

        # Find its components
        donation_components = [
            component
            for component in self.components.values()
            if component["donation_id"] == donation_id
        ]

        # Check donor eligibility
        from src.donor_eligibility import check_donor_eligibility

        donor = self.donors.get(donation["donor_id"])

        if donor is None:
            decision = "DEFERRED"
            failed_rule = "INVALID_DONOR"
        else:
            decision, failed_rule = check_donor_eligibility(
                donor, donation
            )

        self.output_records["donation_eligibility.csv"].append({
            "donation_id": donation_id,
            "donor_id": donation["donor_id"],
            "decision": decision,
            "failed_rule": failed_rule if failed_rule else ""
        })

        # Process every component from this donation
        for component in donation_components:

            unit_id = component["unit_id"]

            if decision != "ACCEPTED":

                status = "DISCARDED"
                reason = "DONOR_INELIGIBLE: " + str(failed_rule)

            else:

                collection_ts = datetime.strptime(
                    donation["collection_ts"],
                    TIMESTAMP_FORMAT
                )

                frozen_ts = None

                if component["frozen_ts"]:
                    frozen_ts = datetime.strptime(
                        component["frozen_ts"],
                        TIMESTAMP_FORMAT
                    )

                expiry = calculate_expiry(
                    component["component"],
                    collection_ts,
                    donation["additive_solution"].lower() == "true",
                    frozen_ts
                )

                if expiry is None:
                    status = "DISCARDED"
                    reason = "INVALID_COMPONENT_EXPIRY"

                else:
                    component["expiry_date"] = expiry.strftime(
                        TIMESTAMP_FORMAT
                    )

                    status = "QUARANTINE"
                    reason = "AWAITING_TTI_SCREENING"

            self.unit_status[unit_id] = {
                "status": status,
                "reason": reason,
                "expiry_date": component.get("expiry_date", "")
            }

            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": status,
                "reason": reason
            })

        print("Donation processed:", donation_id)


    def process_screening(self, donation_id, current_ts):

        # Find the donation
        donation = self.donations.get(donation_id)

        if donation is None:
            print("Donation not found:", donation_id)
            return

        # Get all screening results for this donation
        results = self.screening_results.get(donation_id, [])

        # Get the collection timestamp
        collection_ts = datetime.strptime(
            donation["collection_ts"],
            TIMESTAMP_FORMAT
        )

        current_time = datetime.strptime(
            current_ts,
            TIMESTAMP_FORMAT
        )

        # Check whether any marker is reactive
        reactive = any(
            result["result"].upper() == "REACTIVE"
            for result in results
        )

        # Permanently defer donor if any marker is reactive
        if reactive:

            donor_id = donation["donor_id"]
            donor = self.donors.get(donor_id)

            if donor:
                donor["deferred_until"] = "9999-12-31"

            # Check whether the donation was rejected during eligibility screening
        eligibility_record = next(
            (
                record
                for record in self.output_records["donation_eligibility.csv"]
                if record["donation_id"] == donation_id
            ),
            None
        )

        if eligibility_record and eligibility_record["decision"] == "DEFERRED":

            for component in self.components.values():

                if component["donation_id"] != donation_id:
                    continue

                unit_id = component["unit_id"]

                self.unit_status[unit_id]["status"] = "DISCARDED"
                self.unit_status[unit_id]["reason"] = "DONOR_INELIGIBLE"

                self.output_records["unit_status.csv"].append({
                    "unit_id": unit_id,
                    "ts": current_ts,
                    "status": "DISCARDED",
                    "reason": "DONOR_INELIGIBLE"
                })

            print("Screening skipped: donor was ineligible:", donation_id)
            return

        # Process every component from this donation
        for component in self.components.values():

            if component["donation_id"] != donation_id:
                continue

            unit_id = component["unit_id"]

            # Evaluate screening for this component
            status, permanently_deferred, reason = evaluate_screening(
                collection_ts,
                results,
                component["component"],
                current_time
            )

            # Update inventory status
            if unit_id in self.unit_status:

                self.unit_status[unit_id]["status"] = status
                self.unit_status[unit_id]["reason"] = reason

            else:
                self.unit_status[unit_id] = {
                    "status": status,
                    "reason": reason,
                    "expiry_date": component.get("expiry_date", "")
                }

            # Record the status change
            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": status,
                "reason": reason
            })

        print("Screening processed:", donation_id)
        self.retry_shortage_queue(current_ts)

    def retry_shortage_queue(self, current_ts):
        """Retry pending requests when new stock becomes available."""

        if not self.shortage_queue:
            return

        urgency_order = {
            "EMERGENCY": 0,
            "URGENT": 1,
            "ROUTINE": 2
        }

        pending_requests = sorted(
            self.shortage_queue,
            key=lambda item: (
                urgency_order.get(item["urgency"].upper(), 3),
                item["request_ts"]
            )
        )

        self.shortage_queue = []

        for item in pending_requests:
            request_id = item["request_id"]

            if request_id not in self.request_status:
                continue

            if self.request_status[request_id]["status"] == "CANCELLED":
                continue

            if self.request_status[request_id]["shortfall"] > 0:
                print("Retrying shortage request:", request_id)
                self.process_request(request_id, current_ts)

    def process_request(self, request_id, current_ts):
        """Validate a request and allocate compatible blood units."""

        if request_id not in self.requests:
            print("Invalid request ID:", request_id)
            return False

        request = self.requests[request_id]
        hospital_id = request["hospital_id"]

        if hospital_id not in self.hospitals:
            print("Invalid hospital ID:", hospital_id)
            return False

        units_needed = int(request["units"])
        if units_needed <= 0:
            return False

        urgency = request["urgency"].upper()
        component_type = request["component"].upper()

        if urgency not in ["EMERGENCY", "URGENT", "ROUTINE"]:
            return False

        patient_group = request["patient_group"].upper()
        patient_rh = request["patient_rh"].upper()

        patient_gender = request["patient_gender"].upper()
        patient_age = int(request["patient_age"])

        # Register the request only once.
        # Preserve original timestamp and previous allocations during retries.
        if request_id not in self.request_status:
            self.request_status[request_id] = {
                "status": "PENDING",
                "request_ts": current_ts,
                "hospital_id": hospital_id,
                "component": component_type,
                "requested_units": units_needed,
                "urgency": urgency,
                "shortfall": units_needed,
                "allocated_units": []
            }

        # On retries, allocate only the remaining shortfall.
        units_to_allocate = self.request_status[request_id]["shortfall"]

        # Find units that are currently available
        units_by_group = {}

        for unit_id, component in self.components.items():
        # Skip units already allocated to this request
            if unit_id in self.request_status[request_id]["allocated_units"]:
                continue

            if component["component"].upper() != component_type:
                continue

            status_info = self.unit_status.get(unit_id, {})

            if status_info.get("status") != "AVAILABLE":
                continue

            # Prevent a unit already allocated to another request from being reused.
            already_allocated = any(
                allocation["unit_id"] == unit_id
                and allocation["reservation_state"] in ("ALLOCATED", "CROSSMATCHED")
                for allocation in self.allocations
            )

            if already_allocated:
                continue

            expiry = status_info.get("expiry_date", "")

            if not expiry or expiry < current_ts:
                continue

            donation = self.donations.get(
                component["donation_id"]
            )

            if donation is None:
                continue

            donor = self.donors.get(donation["donor_id"])

            if donor is None:
                continue

            blood_group = donor["blood_group"].upper()
            rh = donor["rh"].upper()

            blood_type = blood_group + (
                "+" if rh in ["POS", "+"] else "-"
            )

            unit_data = dict(component)
            unit_data["unit_id"] = unit_id
            unit_data["expiry_date"] = expiry

            units_by_group.setdefault(
                blood_type, []
            ).append(unit_data)

                # Calculate request SLA deadline
        request_ts = self.request_status[request_id]["request_ts"]

        sla_deadline = calculate_sla_deadline(
            request_ts,
            urgency
        )

        sla_met = (
            datetime.strptime(current_ts, "%Y-%m-%d %H:%M:%S")
            <= datetime.strptime(sla_deadline, "%Y-%m-%d %H:%M:%S")
        )

        allocated_count = 0

        # Allocate only the remaining units
                # Allocate only the remaining units
        for _ in range(units_to_allocate):

            selected = None
            compatibility_path = ""

            if component_type == "PRBC":

                result = allocate_blood_unit(
                    patient_group,
                    patient_rh,
                    units_by_group,
                    emergency=(urgency == "EMERGENCY"),
                    patient_gender=patient_gender,
                    patient_age=patient_age
                )

                if result:
                    selected = result["unit"]
                    selected_blood_type = result["blood_group"]

                    patient_blood_type = patient_group + (
                        "+" if patient_rh in ["POS", "+"] else "-"
                    )

                    if result["reason"] == "EMERGENCY_RH_POS":
                        compatibility_path = "EMERGENCY_RH_POS"

                    elif selected_blood_type == "O-" and patient_blood_type != "O-":
                        compatibility_path = "O_NEG_RESERVE"

                    elif selected_blood_type == patient_blood_type:
                        compatibility_path = "IDENTICAL"

                    else:
                        compatibility_path = "COMPATIBLE_" + selected_blood_type

            elif component_type == "FFP":

                compatible_groups = []

                for blood_type, units in units_by_group.items():

                    donor_group = blood_type[:-1]

                    if (
                        check_ffp_compatibility(donor_group, patient_group)
                        and units
                    ):
                        compatible_groups.append((blood_type, units))

                if compatible_groups:

                    selected_blood_type, selected_units = max(
                        compatible_groups,
                        key=lambda item: len(item[1])
                    )

                    selected = min(
                        selected_units,
                        key=lambda unit: unit["expiry_date"]
                    )

                    compatibility_path = "COMPATIBLE_" + selected_blood_type

            elif component_type == "PLATELET":

                blood_type = patient_group + (
                    "+" if patient_rh in ["POS", "+"] else "-"
                )

                if units_by_group.get(blood_type):
                    selected = min(
                        units_by_group[blood_type],
                        key=lambda unit: unit["expiry_date"]
                    )

                    compatibility_path = "IDENTICAL"

            if selected is None:
                break
            unit_id = selected["unit_id"]

            component = self.components.get(unit_id)

            if component is None:
                continue

            donation_id = component.get("donation_id")
            donation = self.donations.get(donation_id)

            if donation is None:
                continue

            donor_id = donation.get("donor_id")
            donor_record_for_unit = self.donors.get(donor_id)

            if donor_record_for_unit is None:
                continue

            unit_group = donor_record_for_unit["blood_group"]
            unit_rh = donor_record_for_unit["rh"]

            # PRBC units receive a 72-hour reservation
            if component_type == "PRBC":
                reservation = create_reservation(
                    unit_id,
                    request_id,
                    current_ts,
                    urgency=urgency
                )

                self.reservations.append(reservation)
                reservation_state = "CROSSMATCHED"

                self.unit_status.setdefault(
                    unit_id,
                    {
                        "status": "AVAILABLE",
                        "reason": "INITIALIZED_DURING_ALLOCATION"
                    }
                )

                self.unit_status[unit_id]["status"] = "CROSSMATCHED"
                self.unit_status[unit_id]["reason"] = "RESERVED"

            else:
                reservation_state = "ALLOCATED"

            self.request_status[request_id]["allocated_units"].append(unit_id)

            self.allocations.append({
                "request_id": request_id,
                "unit_id": unit_id,
                "unit_group": unit_group,
                "unit_rh": unit_rh,
                "compatibility_path": compatibility_path,
                "reservation_state": reservation_state,
                "allocated_ts": current_ts,
                "sla_met": sla_met,
                "note": ""
            })

            self.output_records["allocations.csv"].append(
                self.allocations[-1]
            )

            # Remove the allocated unit from available stock
            for group_units in units_by_group.values():
                group_units[:] = [
                    unit for unit in group_units
                    if unit["unit_id"] != unit_id
                ]

            allocated_count += 1


    # Calculate remaining shortfall after allocation
        shortfall = units_to_allocate - allocated_count

        self.request_status[request_id]["shortfall"] = shortfall

        total_allocated = len(
                        self.request_status[request_id]["allocated_units"]
                    )

        if shortfall == 0:
                self.request_status[request_id]["status"] = "ALLOCATED"
        elif total_allocated > 0:
                self.request_status[request_id]["status"] = "PARTIAL"
        else:
                self.request_status[request_id]["status"] = "PENDING"

        # Add incomplete requests to the shortage queue only once
        if shortfall > 0:
            existing_queue_entry = next(
                (
                    item for item in self.shortage_queue
                    if item["request_id"] == request_id
                ),
                None
            )

            if existing_queue_entry:
                existing_queue_entry["shortfall"] = shortfall
            else:
                self.shortage_queue.append({
                    "request_id": request_id,
                    "urgency": urgency,
                    "request_ts": self.request_status[request_id]["request_ts"],
                    "shortfall": shortfall
                })
        else:
            # Remove the request if it no longer has a shortfall
            self.shortage_queue = [
                item for item in self.shortage_queue
                if item["request_id"] != request_id
            ]

        print(
            "Request processed:",
            request_id,
            "| Allocated:",
            allocated_count,
            "| Shortfall:",
            shortfall
        )

        return True





    def process_issue(self, request_id, current_ts):

        # Find allocations belonging to this request
        request_allocations = [
            allocation
            for allocation in self.allocations
            if allocation["request_id"] == request_id
            and allocation["reservation_state"] != "ISSUED"
        ]

        if not request_allocations:
            print("No allocated units available to issue:", request_id)
            return False

        issued_count = 0

        for allocation in request_allocations:

            unit_id = allocation["unit_id"]

            # Confirm that the unit exists
            if unit_id not in self.unit_status:
                continue

            current_status = self.unit_status[unit_id]["status"]

            # Check whether the 72-hour reservation has expired
            if current_status == "CROSSMATCHED":

                reservation = next(
                    (
                        r for r in self.reservations
                        if r["unit_id"] == unit_id
                        and r["request_id"] == request_id
                        and r["reservation_state"] == "CROSSMATCHED"
                    ),
                    None
                )

                if reservation:
                    reservation_status = check_reservation_status(
                        reservation, current_ts
                    )

                    if reservation_status == "AVAILABLE":
                        reservation["reservation_state"] = "RELEASED"
                        self.unit_status[unit_id]["status"] = "AVAILABLE"
                        self.unit_status[unit_id]["reason"] = "RESERVATION_EXPIRED"
                        allocation["reservation_state"] = "RELEASED"

                        self.output_records["unit_status.csv"].append({
                            "unit_id": unit_id,
                            "ts": current_ts,
                            "status": "AVAILABLE",
                            "reason": "RESERVATION_EXPIRED"
                        })

                        continue

            # Only available or cross-matched units can be issued
            if current_status not in ["AVAILABLE", "CROSSMATCHED"]:
                continue

            # Update blood unit status
            self.unit_status[unit_id]["status"] = "ISSUED"
            self.unit_status[unit_id]["reason"] = "ISSUED_TO_HOSPITAL"
            self.unit_status[unit_id]["issued_ts"] = current_ts
            self.unit_status[unit_id]["issued_request_id"] = request_id

            # Update allocation record
            allocation["reservation_state"] = "ISSUED"

            # Update cross-match reservation
            for reservation in self.reservations:
                if (
                    reservation["request_id"] == request_id
                    and reservation["unit_id"] == unit_id
                ):
                    reservation["reservation_state"] = "ISSUED"

            # Generate invoice
            request = self.requests[request_id]
            hospital_id = request["hospital_id"]
            hospital_type = self.hospitals[hospital_id]["hospital_type"]

            invoice = calculate_invoice(
                request["component"],
                hospital_type,
                request["urgency"]
            )

            invoice_record = {
                "hospital_id": hospital_id,
                "request_id": request_id,
                "unit_id": unit_id,
                "component": request["component"],
                "base_charge": invoice["base_charge"],
                "government_discount": invoice["government_discount"],
                "emergency_surcharge": invoice["emergency_surcharge"],
                "amount": invoice["amount"]
            }

            self.invoices.append(invoice_record)
            self.output_records["invoices.csv"].append(invoice_record)

            # Record the status change
            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": "ISSUED",
                "reason": "ISSUED_TO_HOSPITAL"
            })

            issued_count += 1

        print("Units issued:", request_id, "| Count:", issued_count)

        return issued_count > 0

    def process_cancel(self, request_id, current_ts):

        if request_id not in self.requests:
            print("Invalid cancellation request:", request_id)
            return False

        if request_id not in self.request_status:
            print("Request has not been processed:", request_id)
            return False

        if self.request_status[request_id].get("status") == "CANCELLED":
            print("Request already cancelled:", request_id)
            return False

        cancelled_count = 0

        for allocation in self.allocations:

            if allocation["request_id"] != request_id:
                continue

            if allocation["reservation_state"] == "ISSUED":
                continue

            unit_id = allocation["unit_id"]

            if unit_id not in self.unit_status:
                continue

            if self.unit_status[unit_id]["status"] == "ISSUED":
                continue

            current_status = self.unit_status[unit_id]["status"]

            if current_status == "CROSSMATCHED":
             self.unit_status[unit_id]["status"] = "AVAILABLE"
             self.unit_status[unit_id]["reason"] = "REQUEST_CANCELLED"

            elif current_status != "AVAILABLE":
             allocation["reservation_state"] = "CANCELLED"
             continue

            allocation["reservation_state"] = "CANCELLED"

            for reservation in self.reservations:

                if (
                    reservation["request_id"] == request_id
                    and reservation["unit_id"] == unit_id
                ):
                    reservation["reservation_state"] = "CANCELLED"

            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": "AVAILABLE",
                "reason": "REQUEST_CANCELLED"
            })

            cancelled_count += 1

        self.request_status[request_id]["status"] = "CANCELLED"
        self.request_status[request_id]["shortfall"] = 0
        # Remove cancelled request from the shortage queue
        self.shortage_queue = [
            item for item in self.shortage_queue
            if item["request_id"] != request_id
        ]

        print(
            "Request cancelled:",
            request_id,
            "| Units released:",
            cancelled_count
        )

        return True


    def process_crossmatch(self, request_id, current_ts, result):

        if request_id not in self.requests:
            print("Invalid cross-match request:", request_id)
            return False

        result = str(result).strip().upper()

        if result not in ["COMPATIBLE", "INCOMPATIBLE"]:
            print("Invalid cross-match result:", result)
            return False

        matching_reservations = [
            reservation
            for reservation in self.reservations
            if reservation["request_id"] == request_id
        ]

        if not matching_reservations:
            print("No reservation found for:", request_id)
            return False

        for reservation in matching_reservations:

            reservation["crossmatch_result"] = result
            reservation["crossmatch_result_ts"] = current_ts

            if result == "INCOMPATIBLE":
                unit_id = reservation["unit_id"]

                if self.unit_status[unit_id]["status"] == "CROSSMATCHED":
                    self.unit_status[unit_id]["status"] = "AVAILABLE"
                    self.unit_status[unit_id]["reason"] = "CROSSMATCH_INCOMPATIBLE"

        print("Cross-match processed:", request_id, "|", result)
        return True


    def process_return(self, request_id, current_ts, units, cold_chain):

        if request_id not in self.requests:
            print("Invalid return request:", request_id)
            return False

        units = int(units)

        if units <= 0:
            print("Invalid return quantity:", request_id)
            return False

        cold_chain = str(cold_chain).strip().lower() == "true"

        # Find units issued under this request
        issued_units = [
            (unit_id, status_info)
            for unit_id, status_info in self.unit_status.items()
            if status_info.get("status") == "ISSUED"
            and status_info.get("issued_request_id") == request_id
        ]

        if len(issued_units) < units:
            print("Not enough issued units to return:", request_id)
            return False

        returned_count = 0

        for unit_id, status_info in issued_units[:units]:

            result = evaluate_return(
                status_info["issued_ts"],
                current_ts,
                cold_chain
            )

            # Remove invoice only if the unit qualifies for a free return
            if result["billable"] is False:

             self.invoices = [
             invoice for invoice in self.invoices
             if not (
            invoice["request_id"] == request_id
            and invoice["unit_id"] == unit_id
        )
    ]

        self.output_records["invoices.csv"] = [
        invoice for invoice in self.output_records["invoices.csv"]
        if not (
            invoice["request_id"] == request_id
            and invoice["unit_id"] == unit_id
        )
    ]

        status =result["status"]

        status_info["status"] = status
        status_info["reason"] = (
                "RETURNED_WITH_COLD_CHAIN"
                if status == "RETURNED"
                else "RETURNED_AFTER_LIMIT_OR_COLD_CHAIN_BROKEN"
            )

            # Update unit status history
        self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": status,
                "reason": status_info["reason"]
            })

        returned_count += 1

        print("Return processed:", unit_id, status)

        print(
            "Return completed:",
            request_id,
            "| Units returned:",
            returned_count
        )

        return returned_count == units

    def process_print_stock(self, report_date):
        """Generate a blood stock report for the requested date."""

        report_date = datetime.strptime(report_date, "%Y-%m-%d")

        stock = {}

        for unit_id, component in self.components.items():

            if unit_id not in self.unit_status:
                continue

            donation_id = component["donation_id"]
            donation = self.donations.get(donation_id)

            if donation is None:
                continue

            donor = self.donors.get(donation["donor_id"])

            if donor is None:
                continue

            blood_group = donor["blood_group"]
            rh = donor["rh"]
            component_type = component["component"]

            key = (blood_group, rh, component_type)

            if key not in stock:
                stock[key] = {
                    "available": 0,
                    "quarantine": 0,
                    "crossmatched": 0
                }

            status = self.unit_status[unit_id]["status"]

            if status in ["AVAILABLE", "RETURNED"]:
                stock[key]["available"] += 1

            elif status == "QUARANTINE":
                stock[key]["quarantine"] += 1

            elif status == "CROSSMATCHED":
                stock[key]["crossmatched"] += 1

        for (blood_group, rh, component_type), counts in stock.items():

            full_group = blood_group + rh

            alert = check_stock_alert(
                counts["available"],
                full_group
            )

            self.output_records["stock_positions.csv"].append({
                "date": report_date,
                "blood_group": blood_group,
                "rh": rh,
                "component": component_type,
                "available": counts["available"],
                "quarantine": counts["quarantine"],
                "crossmatched": counts["crossmatched"],
                "alert": alert
            })

        print("Stock report generated for:", report_date)

    def process_print_invoice(self, hospital_id, from_date, to_date):
        """Display invoices for a hospital within a date range."""

        start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        if start_date > end_date:
            raise ValueError("From date cannot be after to date")

        if hospital_id not in self.hospitals:
            print("Invalid hospital ID:", hospital_id)
            return []

        report = []

        for invoice in self.invoices:

            if invoice["hospital_id"] != hospital_id:
                continue

            matching_allocations = [
                allocation
                for allocation in self.allocations
                if allocation["request_id"] == invoice["request_id"]
                and allocation["unit_id"] == invoice["unit_id"]
            ]

            if not matching_allocations:
                continue

            allocation_date = datetime.strptime(
                matching_allocations[0]["allocated_ts"],
                TIMESTAMP_FORMAT
            ).date()

            if start_date <= allocation_date <= end_date:
                report.append(invoice)

        print("Invoice report for:", hospital_id)
        print("Total invoices:", len(report))

        for invoice in report:
            print(invoice)

        return report

    def process_daily_run(self, run_date):

        """Perform daily inventory maintenance."""

        try:
            report_date = datetime.strptime(run_date, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid daily run date:", run_date)
            return False

        expired_count = 0

        for unit_id, status_info in self.unit_status.items():

            if status_info.get("status") not in ["AVAILABLE", "RETURNED"]:
                continue

            expiry_date = status_info.get("expiry_date")

            if not expiry_date:
                continue

            try:
                expiry = datetime.strptime(
                    expiry_date,
                    TIMESTAMP_FORMAT
                ).date()
            except ValueError:
                continue

            if report_date > expiry:

                status_info["status"] = "EXPIRED"
                status_info["reason"] = "SHELF_LIFE_EXPIRED"

                self.output_records["unit_status.csv"].append({
                    "unit_id": unit_id,
                    "ts": run_date + " 23:59:59",
                    "status": "EXPIRED",
                    "reason": "SHELF_LIFE_EXPIRED"
                })

                expired_count += 1

        # Release unused cross-match reservations that have expired
        run_ts = run_date + " 23:59:59"

        for reservation in self.reservations:

            if reservation["reservation_state"] != "CROSSMATCHED":
                continue

            reservation_status = check_reservation_status(
                reservation, run_ts
            )

            if reservation_status == "AVAILABLE":

                unit_id = reservation["unit_id"]
                request_id = reservation["request_id"]

                reservation["reservation_state"] = "RELEASED"

                self.unit_status[unit_id]["status"] = "AVAILABLE"
                self.unit_status[unit_id]["reason"] = "RESERVATION_EXPIRED"

                for allocation in self.allocations:
                    if (
                        allocation["unit_id"] == unit_id
                        and allocation["request_id"] == request_id
                        and allocation["reservation_state"] == "CROSSMATCHED"
                    ):
                        allocation["reservation_state"] = "RELEASED"

            # Keep the allocation output record in sync
            for output_allocation in self.output_records["allocations.csv"]:
                if (
                    output_allocation["unit_id"] == unit_id
                    and output_allocation["request_id"] == request_id
                ):
                    output_allocation["reservation_state"] = "RELEASED"

                self.output_records["unit_status.csv"].append({
                    "unit_id": unit_id,
                    "ts": run_ts,
                    "status": "AVAILABLE",
                    "reason": "RESERVATION_EXPIRED"
                })

                print("Daily run completed.")
                print("Expired units:", expired_count)

                return True

    def process_commands(self, commands):

     print("\nStarting command execution...")

     for command in commands:

        command_type = command["type"]
        args = command["args"]

        if command_type == "DONATION":
            self.process_donation(
                args["donation_id"],
                args["ts"]
            )

        elif command_type == "SCREENING":
            self.process_screening(
                args["donation_id"],
                args["ts"]
            )

        elif command_type == "REQUEST":
            self.process_request(
                args["request_id"],
                args["ts"]
            )

        elif command_type == "ISSUE":
            self.process_issue(
                args["request_id"],
                args["ts"]
            )

        elif command_type == "CANCEL_REQUEST":
            self.process_cancel(
                args["request_id"],
                args["ts"]
            )

        elif command_type == "RETURN":
            self.process_return(
                args["request_id"],
                args["ts"],
                args["units"],
                args["cold_chain"]
            )

        elif command_type == "CROSSMATCH_RESULT":
            self.process_crossmatch(
                args["request_id"],
                args["ts"],
                args["result"]
            )

        elif command_type == "DAILY_RUN":
            self.process_daily_run(
                args["date"]
            )

        elif command_type == "PRINT_STOCK":
            self.process_print_stock(
                args["date"]
            )

        elif command_type == "PRINT_INVOICE":
            self.process_print_invoice(
                args["hospital_id"],
                args["from_date"],
                args["to_date"]
            )

        else:
            print(
                "Command queued for later implementation:",
                command_type
            )

        print("\nCommand processing completed.")



    def export_outputs(self):

        for filename, records in self.output_records.items():

            output_file = OUTPUT_DIR / filename

            with open(
                output_file,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.DictWriter(
                    file,
                    fieldnames=OUTPUT_FIELDS[filename]
                )

                writer.writeheader()
                writer.writerows(records)

            print("Generated:", filename)
