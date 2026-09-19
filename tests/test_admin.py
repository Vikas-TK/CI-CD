from app import db
from app.models.user import User, Role


def test_admin_dashboard_metrics(client, admin_user, doctor_user, patient_user):
    """Test that admin dashboard displays correct user metrics."""
    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    assert b"Administrator Dashboard" in response.data
    assert b"Total Users" in response.data


def test_admin_user_listing_and_filtering(client, admin_user, doctor_user, patient_user):
    """Test user listing with role and status filtering."""
    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    # All users
    response = client.get("/admin/users")
    assert response.status_code == 200
    assert admin_user.email.encode() in response.data
    assert doctor_user.email.encode() in response.data
    assert patient_user.email.encode() in response.data

    # Filter by role DOCTOR
    doc_filter_res = client.get("/admin/users?role=DOCTOR")
    assert doc_filter_res.status_code == 200
    assert doctor_user.email.encode() in doc_filter_res.data

    # Search filter
    search_res = client.get(f"/admin/users?search={patient_user.first_name}")
    assert search_res.status_code == 200
    assert patient_user.email.encode() in search_res.data


def test_admin_create_privileged_doctor(client, admin_user):
    """Test admin successfully creating a Doctor privileged account."""
    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    payload = {
        "first_name": "Gregory",
        "last_name": "House",
        "email": "dr.house@hospital.org",
        "phone_number": "+15550199999",
        "password": "DiagnosticMaster123!",
        "role": Role.DOCTOR,
        "is_active": "1"
    }

    response = client.post("/admin/users/create", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"created successfully" in response.data

    new_doc = User.query.filter_by(email="dr.house@hospital.org").first()
    assert new_doc is not None
    assert new_doc.role == Role.DOCTOR
    assert new_doc.is_active is True


def test_admin_toggle_user_status(client, admin_user, patient_user):
    """Test admin deactivating and reactivating a user account."""
    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    assert patient_user.is_active is True

    # Deactivate patient
    deactivate_res = client.post(f"/admin/users/{patient_user.user_id}/toggle-status", follow_redirects=True)
    assert deactivate_res.status_code == 200

    updated_patient = db.session.get(User, patient_user.user_id)
    assert updated_patient.is_active is False

    # Reactivate patient
    activate_res = client.post(f"/admin/users/{patient_user.user_id}/toggle-status", follow_redirects=True)
    assert activate_res.status_code == 200

    updated_patient = db.session.get(User, patient_user.user_id)
    assert updated_patient.is_active is True


def test_admin_self_deactivation_protection(client, admin_user):
    """Test that an administrator cannot deactivate their own account."""
    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    response = client.post(f"/admin/users/{admin_user.user_id}/toggle-status", follow_redirects=True)
    assert response.status_code == 200
    assert b"cannot deactivate your own" in response.data

    # Verify admin is still active
    admin_in_db = db.session.get(User, admin_user.user_id)
    assert admin_in_db.is_active is True


def test_admin_change_user_role(client, admin_user, staff_user):
    """Test changing user role by administrator."""
    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    response = client.post(f"/admin/users/{staff_user.user_id}/change-role", data={
        "role": Role.DOCTOR
    }, follow_redirects=True)

    assert response.status_code == 200
    updated_staff = db.session.get(User, staff_user.user_id)
    assert updated_staff.role == Role.DOCTOR


def test_cli_create_admin(runner):
    """Test the Flask CLI command 'create-admin'."""
    result = runner.invoke(args=[
        "create-admin",
        "--email", "cli.admin@hospital.org",
        "--password", "CliAdminPass123!",
        "--first-name", "CLI",
        "--last-name", "Admin",
        "--phone", "+18880001111"
    ])
    assert result.exit_code == 0
    assert "Administrator account 'cli.admin@hospital.org' created successfully" in result.output

    user = User.query.filter_by(email="cli.admin@hospital.org").first()
    assert user is not None
    assert user.role == Role.ADMINISTRATOR


def test_cli_seed_data(runner):
    """Test the Flask CLI command 'seed-data'."""
    result = runner.invoke(args=["seed-data"])
    assert result.exit_code == 0
    assert "Seeded" in result.output
    assert User.query.count() >= 5
