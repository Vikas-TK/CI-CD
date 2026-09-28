import pytest
from app import db
from app.models.ward import Ward, WardType, WardStatus
from app.services.ward_service import WardService


def _login(client, email, password):
    client.get("/auth/logout")
    return client.post("/auth/login", data={"identifier": email, "password": password}, follow_redirects=True)


@pytest.fixture
def sample_wards(app):
    """Populates the database with test wards of varying types, floors, blocks, capacities, and statuses."""
    w1, _ = WardService.create_ward("General Ward Alpha", WardType.GENERAL, 1, "Block A", 30, WardStatus.ACTIVE)
    w2, _ = WardService.create_ward("ICU Central", WardType.ICU, 2, "ICU Wing", 10, WardStatus.ACTIVE)
    w3, _ = WardService.create_ward("Pediatric Ward North", WardType.PEDIATRIC, 2, "Children Wing", 20, WardStatus.ACTIVE)
    w4, _ = WardService.create_ward("Maternity Suite Ward", WardType.MATERNITY, 3, "Women Wing", 15, WardStatus.INACTIVE)
    w5, _ = WardService.create_ward("Surgical Ward West", WardType.SURGICAL, 3, "Surgical Wing", 25, WardStatus.MAINTENANCE)
    return [w1, w2, w3, w4, w5]


# 1. Admin can access Ward management
def test_admin_can_access_ward_management(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards")
    assert response.status_code == 200
    assert b"Hospital Ward Management" in response.data
    assert b"General Ward Alpha" in response.data


# 2. Staff can view wards
def test_staff_can_view_wards(client, staff_user, sample_wards):
    _login(client, staff_user.email, "StaffPassword123!")
    response = client.get("/staff/wards")
    assert response.status_code == 200
    assert b"Hospital Ward Inventory" in response.data
    assert b"General Ward Alpha" in response.data

    # View details as staff
    w1 = sample_wards[0]
    detail_res = client.get(f"/staff/wards/{w1.ward_id}")
    assert detail_res.status_code == 200
    assert b"General Ward Alpha" in detail_res.data
    assert b"30 Beds" in detail_res.data


# 3. Unauthorized users cannot access admin Ward management
def test_unauthorized_users_cannot_access_admin_ward_management(client, patient_user, doctor_user, staff_user, pharmacy_user):
    # Unauthenticated
    client.get("/auth/logout")
    res_unauth = client.get("/admin/wards", follow_redirects=False)
    assert res_unauth.status_code == 302
    assert "/auth/login" in res_unauth.location

    # Patient
    _login(client, patient_user.email, "PatientPassword123!")
    assert client.get("/admin/wards").status_code == 403

    # Doctor
    _login(client, doctor_user.email, "DoctorPassword123!")
    assert client.get("/admin/wards").status_code == 403

    # Staff
    _login(client, staff_user.email, "StaffPassword123!")
    assert client.get("/admin/wards").status_code == 403

    # Pharmacy Manager
    _login(client, pharmacy_user.email, "PharmacyPassword123!")
    assert client.get("/admin/wards").status_code == 403


# 4. Admin can create a Ward
def test_admin_can_create_ward(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "Emergency Rapid Care",
        "ward_type": WardType.EMERGENCY,
        "floor": "1",
        "block": "East Wing",
        "capacity": "18",
        "status": WardStatus.ACTIVE
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Emergency Rapid Care" in response.data

    ward = Ward.query.filter_by(ward_name="Emergency Rapid Care").first()
    assert ward is not None
    assert ward.ward_type == WardType.EMERGENCY
    assert ward.floor == 1
    assert ward.block == "East Wing"
    assert ward.capacity == 18
    assert ward.status == WardStatus.ACTIVE


# 5. Duplicate Ward is rejected
def test_duplicate_ward_is_rejected(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "General Ward Alpha",  # Already exists in sample_wards
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "Block A",
        "capacity": "30",
        "status": WardStatus.ACTIVE
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"already exists" in response.data


# 6. Invalid Ward type is rejected
def test_invalid_ward_type_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "Invalid Type Ward",
        "ward_type": "VIP Penthouse",  # Invalid type
        "floor": "1",
        "block": "Block A",
        "capacity": "10",
        "status": WardStatus.ACTIVE
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Invalid ward type" in response.data


# 7. Invalid Ward status is rejected
def test_invalid_ward_status_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "Invalid Status Ward",
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "Block A",
        "capacity": "10",
        "status": "ClosedPermanently"  # Invalid status
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Invalid ward status" in response.data


# 8. Capacity <= 0 is rejected
def test_capacity_less_equal_zero_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")

    # Zero capacity
    res_zero = client.post("/admin/wards/create", data={
        "ward_name": "Zero Capacity Ward",
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "Block A",
        "capacity": "0",
        "status": WardStatus.ACTIVE
    }, follow_redirects=True)
    assert res_zero.status_code == 400
    assert b"greater than 0" in res_zero.data

    # Negative capacity
    res_neg = client.post("/admin/wards/create", data={
        "ward_name": "Negative Capacity Ward",
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "Block A",
        "capacity": "-5",
        "status": WardStatus.ACTIVE
    }, follow_redirects=True)
    assert res_neg.status_code == 400
    assert b"greater than 0" in res_neg.data


# 9. Missing Ward name is rejected
def test_missing_ward_name_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "",  # Missing name
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "Block A",
        "capacity": "10",
        "status": WardStatus.ACTIVE
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Ward name is required" in response.data


# 10. Missing block is rejected
def test_missing_block_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "No Block Ward",
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "",  # Missing block
        "capacity": "10",
        "status": WardStatus.ACTIVE
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Building block identifier is required" in response.data


# 11. Missing floor is rejected
def test_missing_floor_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "ward_name": "No Floor Ward",
        "ward_type": WardType.GENERAL,
        "floor": "",  # Missing floor
        "block": "Block A",
        "capacity": "10",
        "status": WardStatus.ACTIVE
    }
    response = client.post("/admin/wards/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Floor number is required" in response.data


# 12. Admin can edit a Ward
def test_admin_can_edit_ward(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    w1 = sample_wards[0]

    payload = {
        "ward_name": "General Ward Alpha Renamed",
        "ward_type": WardType.GENERAL,
        "floor": "1",
        "block": "Wing-A-New",
        "capacity": "35",
        "status": WardStatus.MAINTENANCE
    }
    response = client.post(f"/admin/wards/{w1.ward_id}/update", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"General Ward Alpha Renamed" in response.data

    updated = db.session.get(Ward, w1.ward_id)
    assert updated.ward_name == "General Ward Alpha Renamed"
    assert updated.block == "Wing-A-New"
    assert updated.capacity == 35
    assert updated.status == WardStatus.MAINTENANCE


# 13. Admin can view Ward details
def test_admin_can_view_ward_details(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    w1 = sample_wards[0]
    response = client.get(f"/admin/wards/{w1.ward_id}")
    assert response.status_code == 200
    assert b"General Ward Alpha" in response.data
    assert b"30 Beds" in response.data


# 14. Staff cannot modify Ward information
def test_staff_cannot_modify_ward_information(client, staff_user, sample_wards):
    _login(client, staff_user.email, "StaffPassword123!")
    w1 = sample_wards[0]

    # Staff cannot create ward
    res_create = client.post("/admin/wards/create", data={"ward_name": "Staff Ward"}, follow_redirects=True)
    assert res_create.status_code == 403

    # Staff cannot edit ward
    res_edit = client.post(f"/admin/wards/{w1.ward_id}/update", data={"ward_name": "Staff Hack"}, follow_redirects=True)
    assert res_edit.status_code == 403

    # Staff cannot delete ward
    res_delete = client.post(f"/admin/wards/{w1.ward_id}/delete", follow_redirects=True)
    assert res_delete.status_code == 403


# 15. Search by Ward ID works
def test_search_by_ward_id_works(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    w2 = sample_wards[1]  # ICU Central
    response = client.get(f"/admin/wards?search={w2.ward_id}")
    assert response.status_code == 200
    assert b"ICU Central" in response.data


# 16. Search by Ward name works
def test_search_by_ward_name_works(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards?search=Pediatric")
    assert response.status_code == 200
    assert b"Pediatric Ward North" in response.data
    assert b"General Ward Alpha" not in response.data


# 17. Search by Ward type works
def test_search_by_ward_type_works(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards?ward_type=ICU")
    assert response.status_code == 200
    assert b"ICU Central" in response.data
    assert b"General Ward Alpha" not in response.data


# 18. Filter by status works
def test_filter_by_status_works(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards?status=Maintenance")
    assert response.status_code == 200
    assert b"Surgical Ward West" in response.data
    assert b"General Ward Alpha" not in response.data


# 19. Filter by floor works
def test_filter_by_floor_works(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards?floor=2")
    assert response.status_code == 200
    assert b"ICU Central" in response.data
    assert b"Pediatric Ward North" in response.data
    assert b"General Ward Alpha" not in response.data


# 20. Filter by block works
def test_filter_by_block_works(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards?block=Children Wing")
    assert response.status_code == 200
    assert b"Pediatric Ward North" in response.data
    assert b"General Ward Alpha" not in response.data


# 21. Multiple filters work together
def test_multiple_filters_work_together(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    # Type=ICU, Floor=2, Status=Active should match only ICU Central
    response = client.get("/admin/wards?ward_type=ICU&floor=2&status=Active")
    assert response.status_code == 200
    assert b"ICU Central" in response.data
    assert b"Pediatric Ward North" not in response.data
    assert b"General Ward Alpha" not in response.data


# 22. Ward status counts are correct
def test_ward_status_counts_are_correct(sample_wards):
    stats = WardService.get_ward_stats()
    assert stats["total"] == 5
    assert stats["active"] == 3       # General Ward Alpha (30), ICU Central (10), Pediatric (20)
    assert stats["inactive"] == 1     # Maternity (15)
    assert stats["maintenance"] == 1  # Surgical (25)
    assert stats["total_beds"] == 100 # 30 + 10 + 20 + 15 + 25 = 100


# 23. Nonexistent Ward returns an appropriate error
def test_nonexistent_ward_returns_appropriate_error(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/wards/99999", follow_redirects=True)
    assert response.status_code == 200
    assert b"Ward record not found" in response.data


# 24. Unauthorized Ward modification is rejected
def test_unauthorized_ward_modification_is_rejected(client, patient_user, sample_wards):
    _login(client, patient_user.email, "PatientPassword123!")
    w1 = sample_wards[0]
    res = client.post(f"/admin/wards/{w1.ward_id}/update", data={"ward_name": "Hacked Ward"}, follow_redirects=True)
    assert res.status_code == 403


# 25. Ward deletion follows the project's safety rules
def test_ward_deletion_follows_project_safety_rules(client, admin_user, sample_wards):
    _login(client, admin_user.email, "AdminPassword123!")
    w1 = sample_wards[0]

    # Delete ward
    res_delete = client.post(f"/admin/wards/{w1.ward_id}/delete", follow_redirects=True)
    assert res_delete.status_code == 200
    assert b"was successfully removed" in res_delete.data
    assert db.session.get(Ward, w1.ward_id) is None
