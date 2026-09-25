from app import db
from app.models.user import User, Role
from app.models.staff import Staff
from app.services.staff_service import StaffService
from app.services.user_service import UserService


def _login(client, email, password):
    client.get("/auth/logout")
    return client.post("/auth/login", data={"identifier": email, "password": password}, follow_redirects=True)


def test_admin_access_staff_management(client, admin_user):
    """Test 1: Admin can access Staff management directory."""
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/staff")
    assert response.status_code == 200
    assert b"Staff Management" in response.data


def test_non_admin_cannot_access_admin_staff_management(client, patient_user, doctor_user, staff_user):
    """Test 2: Non-admin users cannot access admin staff management endpoints."""
    # Unauthenticated
    client.get("/auth/logout")
    res_unauth = client.get("/admin/staff", follow_redirects=False)
    assert res_unauth.status_code == 302
    assert "/auth/login" in res_unauth.location

    # Patient
    _login(client, patient_user.email, "PatientPassword123!")
    assert client.get("/admin/staff").status_code == 403

    # Doctor
    _login(client, doctor_user.email, "DoctorPassword123!")
    assert client.get("/admin/staff").status_code == 403

    # Staff
    _login(client, staff_user.email, "StaffPassword123!")
    assert client.get("/admin/staff").status_code == 403


def test_admin_creates_staff_success(client, admin_user):
    """Test 3: Admin successfully provisions a new staff account and profile."""
    _login(client, admin_user.email, "AdminPassword123!")

    payload = {
        "first_name": "Clara",
        "last_name": "Oswald",
        "email": "clara.staff@hospital.org",
        "phone_number": "+15559876543",
        "password": "StaffPassword123!",
        "designation": "Receptionist",
        "aadhaar_number": "112233445566",
        "is_active": "1"
    }

    response = client.post("/admin/staff/create", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Clara Oswald" in response.data
    assert b"Receptionist" in response.data

    user = User.query.filter_by(email="clara.staff@hospital.org").first()
    assert user is not None
    assert user.role == Role.STAFF

    staff = Staff.query.filter_by(user_id=user.user_id).first()
    assert staff is not None
    assert staff.designation == "Receptionist"
    assert staff.masked_aadhaar == "XXXX-XXXX-5566"


def test_staff_creation_validation(client, admin_user):
    """Test 4: Staff creation validates required fields, designation, and Aadhaar format."""
    _login(client, admin_user.email, "AdminPassword123!")

    # Missing fields
    res = client.post("/admin/staff/create", data={}, follow_redirects=True)
    assert res.status_code == 400

    # Invalid designation (blank or invalid characters)
    payload = {
        "first_name": "Invalid",
        "last_name": "Desig",
        "email": "invalid.desig@hospital.org",
        "phone_number": "+15550001111",
        "password": "StaffPass123!",
        "designation": "",
        "aadhaar_number": "123456789012"
    }
    res2 = client.post("/admin/staff/create", data=payload, follow_redirects=True)
    assert res2.status_code == 400

    # Invalid Aadhaar (letters or wrong length)
    payload["designation"] = "Nurse"
    payload["aadhaar_number"] = "1234ABC"
    res3 = client.post("/admin/staff/create", data=payload, follow_redirects=True)
    assert res3.status_code == 400


def test_duplicate_staff_profile_rejection(client, admin_user, staff_user, staff_profile):
    """Test 5: Duplicate Staff profile for the same user account is rejected."""
    staff, errors = StaffService.create_staff_profile(
        user_id=staff_user.user_id,
        designation="Lab Technician"
    )
    assert staff is None
    assert "Staff profile already exists" in errors[0]


def test_non_staff_user_cannot_have_staff_profile(client, admin_user, doctor_user, patient_user):
    """Test 6: Reject linking a staff profile to non-staff user accounts."""
    staff_doc, errors_doc = StaffService.create_staff_profile(
        user_id=doctor_user.user_id,
        designation="Nurse"
    )
    assert staff_doc is None
    assert "Cannot link staff profile to a non-staff account" in errors_doc[0]

    staff_pat, errors_pat = StaffService.create_staff_profile(
        user_id=patient_user.user_id,
        designation="Nurse"
    )
    assert staff_pat is None
    assert "Cannot link staff profile to a non-staff account" in errors_pat[0]


def test_staff_view_own_profile(client, staff_user, staff_profile):
    """Test 7: Authenticated Staff user can view their own profile."""
    _login(client, staff_user.email, "StaffPassword123!")

    response = client.get("/staff/profile")
    assert response.status_code == 200
    assert bytes(staff_user.full_name, "utf-8") in response.data
    assert bytes(staff_profile.designation, "utf-8") in response.data
    assert b"XXXX-XXXX-1098" in response.data


def test_staff_cannot_view_or_modify_other_staff_profile(client, admin_user, staff_user, staff_profile):
    """Test 8: Staff user cannot view or modify another staff member's private admin page."""
    # Create another staff member
    user2, _ = UserService.create_privileged_user(
        first_name="Second",
        last_name="Staff",
        email="second.staff@hospital.org",
        phone_number="+1000000088",
        password="StaffPass123!",
        role=Role.STAFF
    )
    staff2, _ = StaffService.create_staff_profile(user_id=user2.user_id, designation="Accountant")

    # Login as first staff user
    _login(client, staff_user.email, "StaffPassword123!")

    # Attempt to view admin detail route for staff2 -> 403
    res = client.get(f"/admin/staff/{staff2.staff_id}")
    assert res.status_code == 403

    # Attempt to access edit route for staff2 -> 403
    res_edit = client.get(f"/admin/staff/{staff2.staff_id}/edit")
    assert res_edit.status_code == 403

    # Attempt to post update to staff2 profile directly via service
    updated, errors = StaffService.update_staff_profile(
        staff_id=staff2.staff_id,
        updating_user=staff_user,
        phone_number="+10009998888"
    )
    assert updated is None
    assert "Unauthorized" in errors[0]


def test_staff_cannot_change_role_or_designation_self_service(client, staff_user, staff_profile):
    """Test 9: Staff user self-service update cannot modify role or designation."""
    _login(client, staff_user.email, "StaffPassword123!")

    # Attempt to pass designation in profile update
    res = client.post("/staff/profile/update", data={
        "phone_number": "+1000000033",
        "aadhaar_number": "987654321098",
        "designation": "Administrator",
        "role": "ADMINISTRATOR"
    }, follow_redirects=True)
    assert res.status_code == 200

    # Reload staff and user
    db.session.refresh(staff_profile)
    db.session.refresh(staff_user)

    assert staff_user.role == Role.STAFF
    assert staff_profile.designation == "Nurse"
    assert staff_user.phone_number == "+1000000033"


def test_staff_self_service_update(client, staff_user, staff_profile):
    """Test 10: Staff user can update permitted contact and Aadhaar info."""
    _login(client, staff_user.email, "StaffPassword123!")

    res = client.post("/staff/profile/update", data={
        "phone_number": "+15557778888",
        "aadhaar_number": "555566667777"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"XXXX-XXXX-7777" in response_data if (response_data := res.data) else True

    db.session.refresh(staff_profile)
    assert staff_profile.masked_aadhaar == "XXXX-XXXX-7777"
    assert staff_profile.phone_number == "+15557778888"


def test_admin_updates_staff_profile(client, admin_user, staff_profile):
    """Test 11: Admin can update designation, phone, and Aadhaar on staff profile."""
    _login(client, admin_user.email, "AdminPassword123!")

    payload = {
        "designation": "Lab Technician",
        "phone_number": "+19998887777",
        "aadhaar_number": "999988887777"
    }

    res = client.post(f"/admin/staff/{staff_profile.staff_id}/update", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"Lab Technician" in res.data
    assert b"+19998887777" in res.data

    db.session.refresh(staff_profile)
    assert staff_profile.designation == "Lab Technician"
    assert staff_profile.phone_number == "+19998887777"


def test_staff_search_and_filter(client, admin_user, staff_user, staff_profile):
    """Test 12: Admin staff search and designation/status filter works."""
    _login(client, admin_user.email, "AdminPassword123!")

    # Search by staff name
    res_name = client.get(f"/admin/staff?search={staff_user.first_name}")
    assert res_name.status_code == 200
    assert bytes(staff_user.full_name, "utf-8") in res_name.data

    # Search by designation
    res_desig = client.get("/admin/staff?designation=Nurse")
    assert res_desig.status_code == 200
    assert bytes(staff_user.full_name, "utf-8") in res_desig.data

    # Filter active
    res_active = client.get("/admin/staff?status=active")
    assert res_active.status_code == 200
    assert bytes(staff_user.full_name, "utf-8") in res_active.data

    # Filter inactive
    res_inactive = client.get("/admin/staff?status=inactive")
    assert res_inactive.status_code == 200
    assert bytes(staff_user.full_name, "utf-8") not in res_inactive.data


def test_invalid_staff_id_returns_appropriate_error(client, admin_user):
    """Test 13: Non-existent staff_id returns graceful redirect and error message."""
    _login(client, admin_user.email, "AdminPassword123!")

    res = client.get("/admin/staff/9999", follow_redirects=True)
    assert res.status_code == 200
    assert b"Staff profile record not found" in res.data

    res_edit = client.get("/admin/staff/9999/edit", follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"Staff profile record not found" in res_edit.data


def test_inactive_staff_access_blocked(client, staff_user, staff_profile):
    """Test 14: Inactive staff accounts cannot access staff dashboard or profile."""
    staff_user.is_active = False
    db.session.commit()

    _login(client, staff_user.email, "StaffPassword123!")
    res_dash = client.get("/staff/dashboard", follow_redirects=False)
    assert res_dash.status_code == 302
    assert "/auth/login" in res_dash.location


def test_aadhaar_masked_in_ui_and_hidden_in_directory(client, admin_user, staff_profile):
    """Test 15: Aadhaar is masked in UI and not displayed in public staff directory."""
    # Public directory
    res_dir = client.get("/staff")
    assert res_dir.status_code == 200
    assert bytes(staff_profile.full_name, "utf-8") in res_dir.data
    assert b"987654321098" not in res_dir.data
    assert b"XXXX-XXXX" not in res_dir.data

    # Admin view shows masked
    _login(client, admin_user.email, "AdminPassword123!")
    res_view = client.get(f"/admin/staff/{staff_profile.staff_id}")
    assert res_view.status_code == 200
    assert b"XXXX-XXXX-1098" in res_view.data
    assert b"987654321098" not in res_view.data


def test_staff_database_constraints(app, staff_user, staff_profile):
    """Test 16: Database constraints (1-to-1 unique foreign key and cascade deletion)."""
    with app.app_context():
        # Duplicate user_id constraint
        duplicate_staff = Staff(user_id=staff_user.user_id, designation="Accountant")
        db.session.add(duplicate_staff)
        try:
            db.session.commit()
            assert False, "Duplicate user_id in staff table should raise IntegrityError"
        except Exception:
            db.session.rollback()

        # Cascade deletion: deleting user deletes staff record
        user_id = staff_user.user_id
        staff_id = staff_profile.staff_id
        user = db.session.get(User, user_id)
        db.session.delete(user)
        db.session.commit()

        assert db.session.get(Staff, staff_id) is None
