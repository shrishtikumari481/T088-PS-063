import csv
from src.request_sla import calculate_sla_deadline
from pathlib import Path
from datetime import datetime, timedelta

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

        # Load daily hospital quotas
        self.hospital_quotas = {
            (item["hospital_id"], item["component"].upper()):
                int(item["daily_cap_units"])
            for item in data.get("hospital_quotas", [])
        }

        # Track daily issued units by hospital and component
        self.daily_issued_units = {}

        # Track monthly mobilised donations
        self.monthly_mobilised_donations = {}

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
        self.platelet_pools = []

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
        # BR-11: If an emergency has no compatible available PRBC stock,
        # pre-empt one routine cross-match reservation.
        if component_type == "PRBC" and urgency == "EMERGENCY":
            available_choice = allocate_blood_unit(
                patient_group, patient_rh, units_by_group,
                emergency=True, patient_gender=patient_gender,
                patient_age=patient_age
            )
            if available_choice is None:
                for reservation in self.reservations:
                    if (
                        reservation.get("reservation_state") != "CROSSMATCHED"
                        or reservation.get("urgency") != "ROUTINE"
                    ):
                        continue
                    reserved_unit_id = reservation["unit_id"]
                    reserved_info = self.unit_status.get(reserved_unit_id, {})
                    if reserved_info.get("status") != "CROSSMATCHED":
                        continue

                    # A reservation at or beyond 72 hours is released normally,
                    # not recorded as an emergency pre-emption.
                    if check_reservation_status(reservation, current_ts) == "AVAILABLE":
                        reservation["reservation_state"] = "RELEASED"
                        reserved_info["status"] = "AVAILABLE"
                        reserved_info["reason"] = "RESERVATION_EXPIRED"
                        for old_alloc in self.allocations:
                            if old_alloc["unit_id"] == reserved_unit_id and old_alloc["request_id"] == reservation["request_id"]:
                                old_alloc["reservation_state"] = "RELEASED"
                        continue

                    reserved_component = self.components.get(reserved_unit_id)
                    if not reserved_component:
                        continue
                    reserved_donation = self.donations.get(reserved_component.get("donation_id"))
                    if not reserved_donation:
                        continue
                    reserved_donor = self.donors.get(reserved_donation.get("donor_id"))
                    if not reserved_donor:
                        continue

                    donor_group = reserved_donor["blood_group"].upper()
                    donor_rh = reserved_donor["rh"].upper()
                    blood_type = donor_group + ("+" if donor_rh in ("POS", "+") else "-")
                    expiry = reserved_info.get("expiry_date", "")
                    if not expiry or expiry < current_ts:
                        continue

                    candidate = dict(reserved_component)
                    candidate["unit_id"] = reserved_unit_id
                    candidate["expiry_date"] = expiry
                    trial_groups = {key: list(value) for key, value in units_by_group.items()}
                    trial_groups.setdefault(blood_type, []).append(candidate)
                    trial_choice = allocate_blood_unit(
                        patient_group, patient_rh, trial_groups,
                        emergency=True, patient_gender=patient_gender,
                        patient_age=patient_age
                    )
                    if not trial_choice or trial_choice["unit"]["unit_id"] != reserved_unit_id:
                        continue

                    old_request_id = reservation["request_id"]
                    reservation["reservation_state"] = "PREEMPTED"
                    reserved_info["status"] = "AVAILABLE"
                    reserved_info["reason"] = "EMERGENCY_PREEMPTION"

                    for old_alloc in self.allocations:
                        if old_alloc["unit_id"] == reserved_unit_id and old_alloc["request_id"] == old_request_id:
                            old_alloc["reservation_state"] = "PREEMPTED"
                    for old_alloc in self.output_records["allocations.csv"]:
                        if old_alloc["unit_id"] == reserved_unit_id and old_alloc["request_id"] == old_request_id:
                            old_alloc["reservation_state"] = "PREEMPTED"

                    old_state = self.request_status.get(old_request_id)
                    if old_state:
                        old_state["allocated_units"] = [
                            item for item in old_state.get("allocated_units", [])
                            if item != reserved_unit_id
                        ]
                        old_state["shortfall"] = old_state.get("shortfall", 0) + 1
                        old_state["status"] = "PARTIAL" if old_state["allocated_units"] else "PENDING"
                        queue_item = next(
                            (item for item in self.shortage_queue if item["request_id"] == old_request_id),
                            None
                        )
                        if queue_item:
                            queue_item["shortfall"] = old_state["shortfall"]
                        else:
                            self.shortage_queue.append({
                                "request_id": old_request_id,
                                "urgency": old_state.get("urgency", "ROUTINE"),
                                "request_ts": old_state.get("request_ts", current_ts),
                                "shortfall": old_state["shortfall"]
                            })

                    self.output_records["unit_status.csv"].append({
                        "unit_id": reserved_unit_id, "ts": current_ts,
                        "status": "AVAILABLE", "reason": "EMERGENCY_PREEMPTION"
                    })
                    units_by_group.setdefault(blood_type, []).append(candidate)
                    break

        # BR-09: Critical stock (<2 units) is reserved for urgent/emergency requests.
        if urgency == "ROUTINE":
            units_by_group = {
                group: group_units
                for group, group_units in units_by_group.items()
                if check_stock_alert(len(group_units), group) != "CRITICAL"
            }

        # BR-12: Multi-unit platelet requests must form a valid same-group pool
        # whose member expiries are all within 24 hours of one another.
        if component_type == "PLATELET" and units_to_allocate > 1:
            platelet_group = patient_group + ("+" if patient_rh in ["POS", "+"] else "-")
            candidates = sorted(
                units_by_group.get(platelet_group, []),
                key=lambda unit: unit["expiry_date"]
            )
            valid_pool = None
            for start_index in range(max(0, len(candidates) - units_to_allocate + 1)):
                window = candidates[start_index:start_index + units_to_allocate]
                if len(window) != units_to_allocate:
                    continue
                pool_units = [
                    {
                        "unit_id": unit["unit_id"],
                        "blood_group": patient_group,
                        "expiry_date": unit["expiry_date"]
                    }
                    for unit in window
                ]
                try:
                    pool_record = create_platelet_pool(pool_units)
                    valid_pool = (window, pool_record)
                    break
                except ValueError:
                    continue
            if valid_pool:
                chosen_units, pool_record = valid_pool
                self.platelet_pools.append({
                    "request_id": request_id,
                    **pool_record
                })
                units_by_group = {platelet_group: chosen_units}
            else:
                units_by_group = {}

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

            # Routine/urgent PRBC allocations are cross-matched and reserved.
            # Emergency PRBC allocations proceed uncrossmatched; retrospective
            # cross-match is tracked after ISSUE (BR-06).
            if component_type == "PRBC" and urgency != "EMERGENCY":
                reservation = create_reservation(
                    unit_id, request_id, current_ts, urgency=urgency
                )
                self.reservations.append(reservation)
                reservation_state = "CROSSMATCHED"
                self.unit_status[unit_id]["status"] = "CROSSMATCHED"
                self.unit_status[unit_id]["reason"] = "RESERVED"
            else:
                reservation_state = "ALLOCATED"

            self.request_status[request_id]["allocated_units"].append(unit_id)

            allocation_record = {
                "request_id": request_id,
                "unit_id": unit_id,
                "unit_group": unit_group,
                "unit_rh": unit_rh,
                "compatibility_path": compatibility_path,
                "reservation_state": reservation_state,
                "allocated_ts": current_ts,
                "sla_met": sla_met,
                "note": ""
            }

            # Reuse a historical row for the same request/unit pair when
            # a released or pre-empted unit is legitimately reallocated.
            existing_allocation = next(
                (
                    item for item in self.allocations
                    if item["request_id"] == request_id
                    and item["unit_id"] == unit_id
                ),
                None
            )
            if existing_allocation:
                existing_allocation.update(allocation_record)
            else:
                self.allocations.append(allocation_record)
                self.output_records["allocations.csv"].append(allocation_record)

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

        # Keep one explicit output row for any remaining shortfall.
        shortfall_row = next(
            (
                row for row in self.output_records["allocations.csv"]
                if row["request_id"] == request_id
                and row.get("reservation_state") == "SHORTFALL"
            ),
            None
        )
        if shortfall > 0:
            shortfall_values = {
                "request_id": request_id,
                "unit_id": "",
                "unit_group": "",
                "unit_rh": "",
                "compatibility_path": "",
                "reservation_state": "SHORTFALL",
                "allocated_ts": current_ts,
                "sla_met": sla_met,
                "note": f"UNFILLED_UNITS:{shortfall}"
            }
            if shortfall_row is None:
                self.output_records["allocations.csv"].append(shortfall_values)
            else:
                shortfall_row.update(shortfall_values)
        elif shortfall_row is not None:
            self.output_records["allocations.csv"].remove(shortfall_row)

        # Emergency PRBC requests are issued immediately without waiting
        # for a cross-match; the retrospective result is tracked separately.
        if component_type == "PRBC" and urgency == "EMERGENCY" and allocated_count > 0:
            self.process_issue(request_id, current_ts)

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

        # BR-08: Enforce hospital quotas when quota data is configured.
        request = self.requests[request_id]
        hospital_id = request["hospital_id"]
        component_type = request["component"].upper()
        urgency = request["urgency"].upper()
        issue_date = current_ts[:10]
        issue_month = current_ts[:7]
        quota_key = (hospital_id, component_type, issue_date)

        # Small unit-test fixtures may omit quota data. In that case,
        # quota enforcement is disabled rather than treating the cap as zero.
        if (hospital_id, component_type) in self.hospital_quotas:
            already_issued_today = self.daily_issued_units.get(quota_key, 0)
            normal_quota = self.hospital_quotas[(hospital_id, component_type)]

            mobilised_donations = sum(
                1 for donation in self.donations.values()
                if donation.get("mobilised_by_hospital_id") == hospital_id
                and donation.get("collection_ts", "")[:7] == issue_month
            )

            monthly_issued = sum(
                1 for unit_info in self.unit_status.values()
                if unit_info.get("issued_ts", "")[:7] == issue_month
                and unit_info.get("issued_request_id") in self.requests
                and self.requests[unit_info["issued_request_id"]]["hospital_id"] == hospital_id
            )

            replacement_ratio = calculate_replacement_ratio(
                monthly_issued, mobilised_donations
            )

            adjusted_quota = normal_quota
            if urgency == "ROUTINE":
                adjusted_quota = calculate_adjusted_quota(
                    normal_quota, replacement_ratio
                )

            quota_result = check_daily_quota(
                adjusted_quota,
                already_issued_today,
                len(request_allocations),
                urgency
            )
            approved_units = quota_result["approved_units"]
        else:
            approved_units = len(request_allocations)

        issued_count = 0
        quota_skipped_allocations = []

        for allocation_index, allocation in enumerate(request_allocations):

            # Preserve unissued units as a queued shortfall when the quota is reached.
            if issued_count >= approved_units:
                quota_skipped_allocations.extend(request_allocations[allocation_index:])
                break

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

            if request["component"].upper() == "PRBC" and request["urgency"].upper() == "EMERGENCY":
                issue_time = datetime.strptime(current_ts, TIMESTAMP_FORMAT)
                self.unit_status[unit_id]["retrospective_crossmatch"] = "PENDING"
                self.unit_status[unit_id]["retrospective_crossmatch_due_ts"] = (
                    issue_time + timedelta(hours=24)
                ).strftime(TIMESTAMP_FORMAT)

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

            # Update hospital's daily issued-unit count
            self.daily_issued_units[quota_key] = (
                self.daily_issued_units.get(quota_key, 0) + 1
            )

        # BR-08: release units beyond the daily quota and queue the shortfall.
        released_for_quota = 0
        for allocation in quota_skipped_allocations:
            unit_id = allocation["unit_id"]
            info = self.unit_status.get(unit_id, {})
            if info.get("status") not in ("AVAILABLE", "CROSSMATCHED"):
                continue
            info["status"] = "AVAILABLE"
            info["reason"] = "HOSPITAL_DAILY_QUOTA_LIMIT"
            allocation["reservation_state"] = "RELEASED"
            allocation["note"] = "HOSPITAL_DAILY_QUOTA_LIMIT"
            for reservation in self.reservations:
                if reservation["request_id"] == request_id and reservation["unit_id"] == unit_id:
                    reservation["reservation_state"] = "RELEASED"
            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id, "ts": current_ts,
                "status": "AVAILABLE", "reason": "HOSPITAL_DAILY_QUOTA_LIMIT"
            })
            if unit_id in self.request_status.get(request_id, {}).get("allocated_units", []):
                self.request_status[request_id]["allocated_units"].remove(unit_id)
            released_for_quota += 1

        if released_for_quota:
            state = self.request_status.get(request_id)
            if state:
                state["shortfall"] = state.get("shortfall", 0) + released_for_quota
                state["status"] = "PARTIAL" if state["allocated_units"] else "PENDING"
                queue_item = next(
                    (item for item in self.shortage_queue if item["request_id"] == request_id),
                    None
                )
                if queue_item:
                    queue_item["shortfall"] = state["shortfall"]
                else:
                    self.shortage_queue.append({
                        "request_id": request_id,
                        "urgency": urgency,
                        "request_ts": state.get("request_ts", current_ts),
                        "shortfall": state["shortfall"]
                    })
                shortfall_row = next(
                    (row for row in self.output_records["allocations.csv"]
                     if row["request_id"] == request_id and row.get("reservation_state") == "SHORTFALL"),
                    None
                )
                values = {
                    "request_id": request_id, "unit_id": "", "unit_group": "",
                    "unit_rh": "", "compatibility_path": "",
                    "reservation_state": "SHORTFALL", "allocated_ts": current_ts,
                    "sla_met": False, "note": f"UNFILLED_UNITS:{state['shortfall']}"
                }
                if shortfall_row:
                    shortfall_row.update(values)
                else:
                    self.output_records["allocations.csv"].append(values)

        print("Units issued:", request_id, "| Count:", issued_count,
              "| Quota shortfall:", released_for_quota)
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
        """Record cross-match results, including emergency retrospective checks."""
        if request_id not in self.requests:
            print("Invalid cross-match request:", request_id)
            return False
        result = str(result).strip().upper()
        if result not in ("COMPATIBLE", "INCOMPATIBLE"):
            print("Invalid cross-match result:", result)
            return False

        matching_reservations = [
            reservation for reservation in self.reservations
            if reservation["request_id"] == request_id
        ]
        emergency_units = [
            (unit_id, info) for unit_id, info in self.unit_status.items()
            if info.get("issued_request_id") == request_id
            and info.get("retrospective_crossmatch") in ("PENDING", "FLAGGED")
        ]

        if not matching_reservations and not emergency_units:
            print("No pending cross-match found for:", request_id)
            return False

        for reservation in matching_reservations:
            reservation["crossmatch_result"] = result
            reservation["crossmatch_result_ts"] = current_ts
            if result == "INCOMPATIBLE":
                unit_id = reservation["unit_id"]
                info = self.unit_status.get(unit_id, {})
                if info.get("status") == "CROSSMATCHED":
                    info["status"] = "AVAILABLE"
                    info["reason"] = "CROSSMATCH_INCOMPATIBLE"
                    reservation["reservation_state"] = "RELEASED"

        for unit_id, info in emergency_units:
            issue_ts = info.get("issued_ts", current_ts)
            state = check_retrospective_crossmatch(issue_ts, current_ts, result)
            info["retrospective_crossmatch"] = state
            info["retrospective_crossmatch_result"] = result
            info["retrospective_crossmatch_ts"] = current_ts
            if result == "INCOMPATIBLE":
                info["reason"] = "RETROSPECTIVE_CROSSMATCH_INCOMPATIBLE"
            elif state == "FLAGGED":
                info["reason"] = "RETROSPECTIVE_CROSSMATCH_OVERDUE"

        print("Cross-match processed:", request_id, "|", result)
        return True

    def process_return(self, request_id, current_ts, units, cold_chain):
        """Process unused units returned by a hospital."""
        if request_id not in self.requests:
            print("Invalid return request:", request_id)
            return False
        try:
            units = int(units)
        except (TypeError, ValueError):
            print("Invalid return quantity:", request_id)
            return False
        if units <= 0:
            print("Invalid return quantity:", request_id)
            return False
        cold_chain = str(cold_chain).strip().lower() in ("true", "1", "yes")
        issued_units = [
            (unit_id, info) for unit_id, info in self.unit_status.items()
            if info.get("status") == "ISSUED" and info.get("issued_request_id") == request_id
        ]
        if len(issued_units) < units:
            print("Not enough issued units to return:", request_id)
            return False
        for unit_id, info in issued_units[:units]:
            try:
                result = evaluate_return(info["issued_ts"], current_ts, cold_chain)
            except (KeyError, TypeError, ValueError) as exc:
                print("Return rejected:", exc)
                return False
            if not result["billable"]:
                self.invoices = [
                    row for row in self.invoices
                    if not (row["request_id"] == request_id and row["unit_id"] == unit_id)
                ]
                self.output_records["invoices.csv"] = [
                    row for row in self.output_records["invoices.csv"]
                    if not (row["request_id"] == request_id and row["unit_id"] == unit_id)
                ]
            status = result["status"]
            info["status"] = status
            info["reason"] = (
                "RETURNED_WITH_COLD_CHAIN" if status == "RETURNED"
                else "RETURNED_AFTER_LIMIT_OR_COLD_CHAIN_BROKEN"
            )
            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id, "ts": current_ts,
                "status": status, "reason": info["reason"]
            })
            print("Return processed:", unit_id, status)
        print("Return completed:", request_id, "| Units returned:", units)
        return True

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
        """Expire stock and release expired reservations at end of run date."""
        try:
            run_time = datetime.strptime(run_date, "%Y-%m-%d") + timedelta(hours=23, minutes=59, seconds=59)
        except (TypeError, ValueError):
            print("Invalid daily run date:", run_date)
            return False
        run_ts = run_time.strftime(TIMESTAMP_FORMAT)
        expired_count = 0
        for unit_id, info in self.unit_status.items():
            if info.get("status") not in ("AVAILABLE", "RETURNED", "CROSSMATCHED"):
                continue
            expiry_text = info.get("expiry_date", "")
            if not expiry_text:
                continue
            try:
                is_expired = datetime.strptime(expiry_text, TIMESTAMP_FORMAT) <= run_time
            except ValueError:
                continue
            if is_expired:
                info["status"] = "EXPIRED"
                info["reason"] = "SHELF_LIFE_EXPIRED"
                self.output_records["unit_status.csv"].append({
                    "unit_id": unit_id, "ts": run_ts,
                    "status": "EXPIRED", "reason": "SHELF_LIFE_EXPIRED"
                })
                expired_count += 1

        released_count = 0
        for reservation in self.reservations:
            if reservation.get("reservation_state") != "CROSSMATCHED":
                continue
            if check_reservation_status(reservation, run_ts) != "AVAILABLE":
                continue
            unit_id = reservation["unit_id"]
            request_id = reservation["request_id"]
            reservation["reservation_state"] = "RELEASED"
            info = self.unit_status.get(unit_id)
            if info and info.get("status") == "CROSSMATCHED":
                expiry_text = info.get("expiry_date", "")
                try:
                    expired = bool(expiry_text) and datetime.strptime(expiry_text, TIMESTAMP_FORMAT) <= run_time
                except ValueError:
                    expired = False
                info["status"] = "EXPIRED" if expired else "AVAILABLE"
                info["reason"] = "SHELF_LIFE_EXPIRED" if expired else "RESERVATION_EXPIRED"
                self.output_records["unit_status.csv"].append({
                    "unit_id": unit_id, "ts": run_ts,
                    "status": info["status"], "reason": info["reason"]
                })
            for record in self.allocations + self.output_records["allocations.csv"]:
                if record["unit_id"] == unit_id and record["request_id"] == request_id:
                    record["reservation_state"] = "RELEASED"
            released_count += 1

        # Flag emergency issues with no retrospective cross-match within 24 hours.
        for unit_id, info in self.unit_status.items():
            if info.get("retrospective_crossmatch") != "PENDING":
                continue
            due_ts = info.get("retrospective_crossmatch_due_ts")
            if due_ts and due_ts <= run_ts:
                info["retrospective_crossmatch"] = "FLAGGED"
                info["reason"] = "RETROSPECTIVE_CROSSMATCH_OVERDUE"
                self.output_records["unit_status.csv"].append({
                    "unit_id": unit_id, "ts": run_ts,
                    "status": info.get("status", "ISSUED"),
                    "reason": "RETROSPECTIVE_CROSSMATCH_OVERDUE"
                })

        print("Daily run completed.")
        print("Expired units:", expired_count)
        print("Released reservations:", released_count)
        return True

    def process_commands(self, commands):
        """Execute commands in their supplied order."""
        print("\\nStarting command execution...")
        for command in commands:
            command_type = command["type"]
            args = command["args"]
            if command_type == "DONATION":
                self.process_donation(args["donation_id"], args["ts"])
            elif command_type == "SCREENING":
                self.process_screening(args["donation_id"], args["ts"])
            elif command_type == "REQUEST":
                self.process_request(args["request_id"], args["ts"])
            elif command_type == "ISSUE":
                self.process_issue(args["request_id"], args["ts"])
            elif command_type == "CANCEL_REQUEST":
                self.process_cancel(args["request_id"], args["ts"])
            elif command_type == "RETURN":
                self.process_return(args["request_id"], args["ts"], args["units"], args["cold_chain"])
            elif command_type == "CROSSMATCH_RESULT":
                self.process_crossmatch(args["request_id"], args["ts"], args["result"])
            elif command_type == "DAILY_RUN":
                self.process_daily_run(args["date"])
            elif command_type == "PRINT_STOCK":
                self.process_print_stock(args["date"])
            elif command_type == "PRINT_INVOICE":
                self.process_print_invoice(args["hospital_id"], args["from_date"], args["to_date"])
            else:
                print("Unsupported command:", command_type)
        print("\\nCommand processing completed.")

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
                    fieldnames=OUTPUT_FIELDS[filename],
                    lineterminator="\n"
                )

                writer.writeheader()
                writer.writerows(records)

            print("Generated:", filename)
