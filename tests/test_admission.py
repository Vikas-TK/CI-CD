from datetime import datetime, timezone
import pytest
from app import db
from app.models.admission import Admission, AdmissionStatus
from app.models.room import Room, RoomType, RoomStatus
from app.models.ward import Ward, WardType, WardStatus
from app.services.admission_service import AdmissionService
from app.services.room_service import RoomService
from app.services.ward_service import WardService
from app.services.patient_service import PatientService
from app.services.user_service import UserService


def _login(client, email, password):
    client.get("/auth/logout")
    return client.post("/auth/login", data={"identifier": email, "password": password}, follow_redirects=True)


@pytest.fixture
def admission_setup(app, patient_profile):
    """Creates a sample active ward, available rooms, and an additional patient profile."""
    ward_active, _ = WardService.create_ward("General Medical Ward", WardType.GENERAL, 1, "Block A", 2, WardStatus.ACTIVE)
    ward_inactive, _ = WardService.create_ward("Renovation Ward", WardType.SURGICAL, 2, "Block B", 5, WardStatus.INACTIVE)

    room_avail_1, _ = RoomService.create_room("101", RoomType.SINGLE, 1, "Block A", RoomStatus.AVAILABLE)
    room_avail_2, _ = RoomService.create_room("102", RoomType.SINGLE, 1, "Block A", RoomStatus.AVAILABLE)
    room_maint, _ = RoomService.create_room("103", RoomType.SINGLE, 1, "Block A", RoomStatus.MAINTENANCE)

    # Second patient
    user2, _ = UserService.register_patient("Bob", "Miller", "bob.miller@hospital.org", "+1000000088", "BobPassword123!", "BobPassword123!")
    patient_2, _ = PatientService.create_patient_profile(user2.user_id, 45, "Male", "998877665544", "B+", "Pneumonia", "Mary Miller", "+1000000087", "456 Oak St")

    return {
        "ward_active": ward_active,
        "ward_inactive": ward_inactive,
        "room_1": room_avail_1,
        "room_2": room_avail_2,
        "room_maint": room_maint,
        "patient_1": patient_profile,
        "patient_2": patient_2
    }


# 1. Admin can create admission
def test_admin_can_create_admission(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    response = client.post("/admin/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": r.room_id,
        "ward_id": w.ward_id,
        "reason": "Acute chest infection."
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"successfully admitted" in response.data
    assert b"#ADM0001" in response.data or b"ADM0001" in response.data or b"ADM" in response.data


# 2. Staff can create admission
def test_staff_can_create_admission(client, staff_user, admission_setup):
    _login(client, staff_user.email, "StaffPassword123!")
    p = admission_setup["patient_2"]
    r = admission_setup["room_2"]
    w = admission_setup["ward_active"]

    response = client.post("/staff/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": r.room_id,
        "ward_id": w.ward_id,
        "reason": "Observation required."
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"successfully admitted" in response.data


# 3. Unauthorized users cannot create admission
def test_unauthorized_users_cannot_create_admission(client, patient_user, doctor_user, pharmacy_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]
    data = {"patient_id": p.patient_id, "room_id": r.room_id, "ward_id": w.ward_id}

    # Patient
    _login(client, patient_user.email, "PatientPassword123!")
    assert client.post("/admin/admissions/create", data=data).status_code == 403
    assert client.post("/staff/admissions/create", data=data).status_code == 403

    # Doctor
    _login(client, doctor_user.email, "DoctorPassword123!")
    assert client.post("/admin/admissions/create", data=data).status_code == 403
    assert client.post("/staff/admissions/create", data=data).status_code == 403

    # Pharmacy Manager
    _login(client, pharmacy_user.email, "PharmacyPassword123!")
    assert client.post("/admin/admissions/create", data=data).status_code == 403
    assert client.post("/staff/admissions/create", data=data).status_code == 403


# 4. Patient must exist
def test_patient_must_exist(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    response = client.post("/admin/admissions/create", data={
        "patient_id": 99999,
        "room_id": r.room_id,
        "ward_id": w.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"Patient record not found" in response.data


# 5. Room must exist
def test_room_must_exist(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p = admission_setup["patient_1"]
    w = admission_setup["ward_active"]

    response = client.post("/admin/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": 99999,
        "ward_id": w.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"Selected room not found" in response.data


# 6. Ward must exist
def test_ward_must_exist(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]

    response = client.post("/admin/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": r.room_id,
        "ward_id": 99999
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"Selected ward not found" in response.data


# 7. Occupied room cannot be assigned
def test_occupied_room_cannot_be_assigned(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p1 = admission_setup["patient_1"]
    p2 = admission_setup["patient_2"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    # First admission succeeds
    AdmissionService.admit_patient(p1.patient_id, r.room_id, w.ward_id)

    # Second patient tries same occupied room
    response = client.post("/admin/admissions/create", data={
        "patient_id": p2.patient_id,
        "room_id": r.room_id,
        "ward_id": w.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"not available for admission" in response.data


# 8. Maintenance room cannot be assigned
def test_maintenance_room_cannot_be_assigned(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p = admission_setup["patient_1"]
    r_maint = admission_setup["room_maint"]
    w = admission_setup["ward_active"]

    response = client.post("/admin/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": r_maint.room_id,
        "ward_id": w.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"not available for admission" in response.data


# 9. Inactive ward cannot be assigned
def test_inactive_ward_cannot_be_assigned(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w_inactive = admission_setup["ward_inactive"]

    response = client.post("/admin/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": r.room_id,
        "ward_id": w_inactive.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"not currently active for new admissions" in response.data


# 10. Full ward cannot accept another patient
def test_full_ward_cannot_accept_another_patient(client, admin_user, admission_setup):
    p1 = admission_setup["patient_1"]
    p2 = admission_setup["patient_2"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]  # Capacity = 2

    # Admit 2 patients to fill capacity (2/2)
    AdmissionService.admit_patient(p1.patient_id, r1.room_id, w.ward_id)
    AdmissionService.admit_patient(p2.patient_id, r2.room_id, w.ward_id)

    # 3rd patient
    u3, _ = UserService.register_patient("Charlie", "Chap", "charlie@hospital.org", "+1000000077", "Pass123!", "Pass123!")
    p3, _ = PatientService.create_patient_profile(u3.user_id, 50, "Male", "554433221100")
    r3, _ = RoomService.create_room("104", RoomType.SINGLE, 1, "Block A", RoomStatus.AVAILABLE)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.post("/admin/admissions/create", data={
        "patient_id": p3.patient_id,
        "room_id": r3.room_id,
        "ward_id": w.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"reached its maximum bed capacity" in response.data


# 11. Patient cannot have two active admissions
def test_patient_cannot_have_two_active_admissions(client, admin_user, admission_setup):
    _login(client, admin_user.email, "AdminPassword123!")
    p = admission_setup["patient_1"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]

    # Admit patient 1st time
    AdmissionService.admit_patient(p.patient_id, r1.room_id, w.ward_id)

    # Try admitting same patient 2nd time while active
    response = client.post("/admin/admissions/create", data={
        "patient_id": p.patient_id,
        "room_id": r2.room_id,
        "ward_id": w.ward_id
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"already has an active admission" in response.data


# 12. Successful admission sets room to Occupied
def test_successful_admission_sets_room_to_occupied(admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    assert r.status == RoomStatus.AVAILABLE
    adm, errors = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    assert errors == []
    assert adm is not None
    updated_room = db.session.get(Room, r.room_id)
    assert updated_room.status == RoomStatus.OCCUPIED


# 13. Successful admission creates Active record
def test_successful_admission_creates_active_record(admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, errors = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id, reason="Chest pain")
    assert errors == []
    assert adm.status == AdmissionStatus.ACTIVE
    assert adm.is_active is True
    assert adm.check_out_date is None


# 14. Patient can view own admission
def test_patient_can_view_own_admission(client, patient_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, patient_user.email, "PatientPassword123!")
    response = client.get("/patient/admission")
    assert response.status_code == 200
    assert b"Active Hospital Admission" in response.data
    assert b"Room 101" in response.data or b"101" in response.data


# 15. Patient cannot view another patient's admission
def test_patient_cannot_view_another_patient_admission(client, admission_setup):
    p2 = admission_setup["patient_2"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p2.patient_id, r.room_id, w.ward_id)

    # Login as patient_1 and verify they cannot access admin/staff views
    u1 = admission_setup["patient_1"].user
    _login(client, u1.email, "PatientPassword123!")
    assert client.get(f"/admin/admissions/{adm.admission_id}").status_code == 403
    assert client.get(f"/staff/admissions/{adm.admission_id}").status_code == 403


# 16. Doctor can view permitted admission information
def test_doctor_can_view_permitted_admission_information(client, doctor_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, doctor_user.email, "DoctorPassword123!")
    list_res = client.get("/doctor/admissions")
    assert list_res.status_code == 200
    assert b"Inpatient Admissions Registry" in list_res.data

    detail_res = client.get(f"/doctor/admissions/{adm.admission_id}")
    assert detail_res.status_code == 200
    assert b"Inpatient Clinical Chart" in detail_res.data


# 17. Unauthorized users cannot access admin admission routes
def test_unauthorized_users_cannot_access_admin_admission_routes(client, patient_user, doctor_user, staff_user):
    # Patient
    _login(client, patient_user.email, "PatientPassword123!")
    assert client.get("/admin/admissions").status_code == 403
    assert client.get("/admin/admissions/create").status_code == 403

    # Doctor
    _login(client, doctor_user.email, "DoctorPassword123!")
    assert client.get("/admin/admissions").status_code == 403

    # Staff
    _login(client, staff_user.email, "StaffPassword123!")
    assert client.get("/admin/admissions").status_code == 403


# 18. Discharge changes status to Discharged
def test_discharge_changes_status_to_discharged(client, admin_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.post(f"/admin/admissions/{adm.admission_id}/discharge", data={
        "discharge_notes": "Recovered well, discharge advised."
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"discharged successfully" in response.data

    updated_adm = db.session.get(Admission, adm.admission_id)
    assert updated_adm.status == AdmissionStatus.DISCHARGED
    assert updated_adm.is_discharged is True


# 19. Discharge records checkout date
def test_discharge_records_checkout_date(admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)
    assert adm.check_out_date is None

    discharged_adm, errors = AdmissionService.discharge_patient(adm.admission_id)
    assert errors == []
    assert discharged_adm.check_out_date is not None


# 20. Discharge releases room
def test_discharge_releases_room(admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)
    assert db.session.get(Room, r.room_id).status == RoomStatus.OCCUPIED

    AdmissionService.discharge_patient(adm.admission_id)
    assert db.session.get(Room, r.room_id).status == RoomStatus.AVAILABLE


# 21. Admission history remains after discharge
def test_admission_history_remains_after_discharge(client, patient_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id, reason="Past infection")
    AdmissionService.discharge_patient(adm.admission_id)

    _login(client, patient_user.email, "PatientPassword123!")
    response = client.get("/patient/admissions/history")
    assert response.status_code == 200
    assert b"My Inpatient Stay History" in response.data
    assert b"Past infection" in response.data


# 22. Invalid discharge is rejected
def test_invalid_discharge_is_rejected(admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)
    AdmissionService.discharge_patient(adm.admission_id)

    # Re-discharging already discharged record
    _, errors = AdmissionService.discharge_patient(adm.admission_id)
    assert "Cannot discharge" in errors[0]

    # Nonexistent admission
    _, errors2 = AdmissionService.discharge_patient(99999)
    assert "Admission record not found" in errors2[0]


# 23. Search by patient works
def test_search_by_patient_works(client, admin_user, admission_setup):
    p1 = admission_setup["patient_1"]
    p2 = admission_setup["patient_2"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]

    AdmissionService.admit_patient(p1.patient_id, r1.room_id, w.ward_id)
    AdmissionService.admit_patient(p2.patient_id, r2.room_id, w.ward_id)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get(f"/admin/admissions?search={p2.full_name}")
    assert response.status_code == 200
    assert p2.full_name.encode() in response.data


# 24. Search by room works
def test_search_by_room_works(client, admin_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]  # Room 101
    w = admission_setup["ward_active"]

    AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/admissions?search=101")
    assert response.status_code == 200
    assert b"Room 101" in response.data or b"101" in response.data


# 25. Search by admission ID works
def test_search_by_admission_id_works(client, admin_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get(f"/admin/admissions?search={adm.admission_id}")
    assert response.status_code == 200
    assert p.full_name.encode() in response.data


# 26. Status filter works
def test_status_filter_works(client, admin_user, admission_setup):
    p1 = admission_setup["patient_1"]
    p2 = admission_setup["patient_2"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]

    adm1, _ = AdmissionService.admit_patient(p1.patient_id, r1.room_id, w.ward_id)
    adm2, _ = AdmissionService.admit_patient(p2.patient_id, r2.room_id, w.ward_id)
    AdmissionService.discharge_patient(adm1.admission_id)

    _login(client, admin_user.email, "AdminPassword123!")
    res_active = client.get("/admin/admissions?status=Active")
    assert res_active.status_code == 200
    assert p2.full_name.encode() in res_active.data

    res_discharged = client.get("/admin/admissions?status=Discharged")
    assert res_discharged.status_code == 200
    assert p1.full_name.encode() in res_discharged.data


# 27. Ward filter works
def test_ward_filter_works(client, admin_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get(f"/admin/admissions?ward_id={w.ward_id}")
    assert response.status_code == 200
    assert w.ward_name.encode() in response.data


# 28. Multiple filters work
def test_multiple_filters_work(client, admin_user, admission_setup):
    p = admission_setup["patient_1"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    AdmissionService.admit_patient(p.patient_id, r.room_id, w.ward_id)

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get(f"/admin/admissions?status=Active&ward_id={w.ward_id}&search={p.full_name}")
    assert response.status_code == 200
    assert p.full_name.encode() in response.data


# 29. Ward capacity calculation works
def test_ward_capacity_calculation_works(admission_setup):
    p1 = admission_setup["patient_1"]
    p2 = admission_setup["patient_2"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]  # Capacity = 2

    occ0 = AdmissionService.get_ward_occupancy(w.ward_id)
    assert occ0["capacity"] == 2
    assert occ0["occupied"] == 0
    assert occ0["available"] == 2
    assert occ0["is_full"] is False

    adm1, _ = AdmissionService.admit_patient(p1.patient_id, r1.room_id, w.ward_id)
    occ1 = AdmissionService.get_ward_occupancy(w.ward_id)
    assert occ1["occupied"] == 1
    assert occ1["available"] == 1
    assert occ1["is_full"] is False

    adm2, _ = AdmissionService.admit_patient(p2.patient_id, r2.room_id, w.ward_id)
    occ2 = AdmissionService.get_ward_occupancy(w.ward_id)
    assert occ2["occupied"] == 2
    assert occ2["available"] == 0
    assert occ2["is_full"] is True

    # Discharge patient 1 -> capacity freed
    AdmissionService.discharge_patient(adm1.admission_id)
    occ3 = AdmissionService.get_ward_occupancy(w.ward_id)
    assert occ3["occupied"] == 1
    assert occ3["available"] == 1
    assert occ3["is_full"] is False


# 30. Duplicate room allocation is prevented
def test_duplicate_room_allocation_is_prevented(admission_setup):
    p1 = admission_setup["patient_1"]
    p2 = admission_setup["patient_2"]
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    adm1, err1 = AdmissionService.admit_patient(p1.patient_id, r.room_id, w.ward_id)
    assert err1 == []

    adm2, err2 = AdmissionService.admit_patient(p2.patient_id, r.room_id, w.ward_id)
    assert adm2 is None
    assert "not available" in err2[0]


# 31. Database transaction rolls back correctly when admission fails
def test_database_transaction_rolls_back_correctly_when_admission_fails(admission_setup):
    r = admission_setup["room_1"]
    w = admission_setup["ward_active"]

    initial_admissions_count = Admission.query.count()
    initial_room_status = db.session.get(Room, r.room_id).status

    # Attempt admission with invalid patient id
    adm, errors = AdmissionService.admit_patient(99999, r.room_id, w.ward_id)
    assert adm is None
    assert errors != []

    assert Admission.query.count() == initial_admissions_count
    assert db.session.get(Room, r.room_id).status == initial_room_status


# 32. Unauthorized transfer is rejected
def test_unauthorized_transfer_is_rejected(client, patient_user, doctor_user, staff_user, admission_setup):
    p = admission_setup["patient_1"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r1.room_id, w.ward_id)

    # Patient
    _login(client, patient_user.email, "PatientPassword123!")
    assert client.post(f"/admin/admissions/{adm.admission_id}/transfer", data={"new_room_id": r2.room_id}).status_code == 403

    # Doctor
    _login(client, doctor_user.email, "DoctorPassword123!")
    assert client.post(f"/admin/admissions/{adm.admission_id}/transfer", data={"new_room_id": r2.room_id}).status_code == 403

    # Staff (Transfer is admin-only in our route design)
    _login(client, staff_user.email, "StaffPassword123!")
    assert client.post(f"/admin/admissions/{adm.admission_id}/transfer", data={"new_room_id": r2.room_id}).status_code == 403


# 33. Valid transfer updates allocation correctly
def test_valid_transfer_updates_allocation_correctly(client, admin_user, admission_setup):
    p = admission_setup["patient_1"]
    r1 = admission_setup["room_1"]
    r2 = admission_setup["room_2"]
    w = admission_setup["ward_active"]

    adm, _ = AdmissionService.admit_patient(p.patient_id, r1.room_id, w.ward_id)
    assert db.session.get(Room, r1.room_id).status == RoomStatus.OCCUPIED
    assert db.session.get(Room, r2.room_id).status == RoomStatus.AVAILABLE

    _login(client, admin_user.email, "AdminPassword123!")
    response = client.post(f"/admin/admissions/{adm.admission_id}/transfer", data={
        "new_room_id": r2.room_id,
        "new_ward_id": w.ward_id,
        "transfer_notes": "Patient requested window bed."
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"transferred successfully" in response.data

    # Verify old room is released, new room is occupied
    assert db.session.get(Room, r1.room_id).status == RoomStatus.AVAILABLE
    assert db.session.get(Room, r2.room_id).status == RoomStatus.OCCUPIED

    updated_adm = db.session.get(Admission, adm.admission_id)
    assert updated_adm.room_id == r2.room_id
