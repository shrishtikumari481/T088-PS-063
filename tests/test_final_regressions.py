from src.inventory_engine import InventoryEngine


def base_data(**overrides):
    data = {
        "donors": [],
        "donations": [],
        "hospitals": [{"hospital_id": "H1", "hospital_type": "PRIVATE"}],
        "requests": [{
            "request_id": "R1", "hospital_id": "H1",
            "component": "PRBC", "urgency": "ROUTINE",
            "units": "3", "patient_group": "A", "patient_rh": "POS",
            "patient_gender": "F", "patient_age": "30"
        }],
        "components": [],
        "screening_results": [],
    }
    data.update(overrides)
    return data


def test_engine_accepts_legacy_fixture_without_quota_file():
    engine = InventoryEngine(base_data())
    assert engine.hospital_quotas == {}


def test_daily_run_releases_all_expired_reservations():
    engine = InventoryEngine(base_data())
    engine.unit_status = {
        "U1": {"status": "CROSSMATCHED", "reason": "RESERVED",
               "expiry_date": "2027-01-01 23:59:00"},
        "U2": {"status": "CROSSMATCHED", "reason": "RESERVED",
               "expiry_date": "2027-01-01 23:59:00"},
    }
    engine.reservations = [
        {"unit_id": "U1", "request_id": "R1",
         "reservation_state": "CROSSMATCHED",
         "release_ts": "2026-11-01 10:00:00"},
        {"unit_id": "U2", "request_id": "R1",
         "reservation_state": "CROSSMATCHED",
         "release_ts": "2026-11-01 10:00:00"},
    ]
    engine.allocations = [
        {"unit_id": "U1", "request_id": "R1", "reservation_state": "CROSSMATCHED"},
        {"unit_id": "U2", "request_id": "R1", "reservation_state": "CROSSMATCHED"},
    ]
    engine.output_records["allocations.csv"] = [dict(x) for x in engine.allocations]

    assert engine.process_daily_run("2026-11-02") is True
    assert engine.unit_status["U1"]["status"] == "AVAILABLE"
    assert engine.unit_status["U2"]["status"] == "AVAILABLE"
    assert all(r["reservation_state"] == "RELEASED" for r in engine.reservations)


def test_routine_issue_obeys_daily_quota_and_queues_remainder():
    data = base_data(hospital_quotas=[
        {"hospital_id": "H1", "component": "PRBC", "daily_cap_units": "2"}
    ])
    engine = InventoryEngine(data)
    engine.unit_status = {
        f"U{i}": {"status": "AVAILABLE", "reason": "TEST"}
        for i in range(1, 4)
    }
    engine.allocations = [
        {
            "request_id": "R1", "unit_id": f"U{i}",
            "reservation_state": "ALLOCATED",
            "allocated_ts": "2026-11-12 09:00:00",
            "unit_group": "A", "unit_rh": "POS",
            "compatibility_path": "IDENTICAL", "sla_met": True, "note": ""
        }
        for i in range(1, 4)
    ]
    engine.output_records["allocations.csv"] = [dict(x) for x in engine.allocations]
    engine.request_status["R1"] = {
        "status": "ALLOCATED", "request_ts": "2026-11-12 09:00:00",
        "hospital_id": "H1", "component": "PRBC",
        "requested_units": 3, "urgency": "ROUTINE",
        "shortfall": 0, "allocated_units": ["U1", "U2", "U3"]
    }

    result = engine.process_issue("R1", "2026-11-12 09:10:00")

    assert result is True
    assert sum(x["status"] == "ISSUED" for x in engine.unit_status.values()) == 2
    assert engine.unit_status["U3"]["status"] == "AVAILABLE"
    assert engine.request_status["R1"]["shortfall"] == 1
    assert any(x["request_id"] == "R1" for x in engine.shortage_queue)


def test_emergency_issue_tracks_retrospective_crossmatch():
    data = base_data()
    data["requests"][0]["urgency"] = "EMERGENCY"
    engine = InventoryEngine(data)
    engine.unit_status = {"U1": {"status": "AVAILABLE", "reason": "TEST"}}
    engine.allocations = [{
        "request_id": "R1", "unit_id": "U1",
        "reservation_state": "ALLOCATED",
        "allocated_ts": "2026-11-12 09:00:00",
        "unit_group": "A", "unit_rh": "POS",
        "compatibility_path": "IDENTICAL", "sla_met": True, "note": ""
    }]
    engine.output_records["allocations.csv"] = [dict(x) for x in engine.allocations]

    assert engine.process_issue("R1", "2026-11-12 09:10:00") is True
    assert engine.unit_status["U1"]["retrospective_crossmatch"] == "PENDING"
    assert engine.process_crossmatch("R1", "2026-11-12 10:00:00", "COMPATIBLE") is True
    assert engine.unit_status["U1"]["retrospective_crossmatch"] == "COMPLETED"
