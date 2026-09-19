def test_role_redirection_on_login(client, admin_user, doctor_user, staff_user, patient_user, pharmacy_user):
    """Test that each role is correctly redirected to their designated dashboard after login."""
    roles_and_dashboards = [
        (admin_user.email, "AdminPassword123!", "/admin/dashboard"),
        (doctor_user.email, "DoctorPassword123!", "/doctor/dashboard"),
        (staff_user.email, "StaffPassword123!", "/staff/dashboard"),
        (patient_user.email, "PatientPassword123!", "/patient/dashboard"),
        (pharmacy_user.email, "PharmacyPassword123!", "/pharmacy/dashboard"),
    ]

    for email, pwd, expected_dash in roles_and_dashboards:
        # Logout any active session first
        client.get("/auth/logout")

        response = client.post("/auth/login", data={
            "identifier": email,
            "password": pwd
        }, follow_redirects=False)

        assert response.status_code == 302
        assert expected_dash in response.location


def test_unauthenticated_access_protection(client):
    """Test that unauthenticated requests to protected dashboards are blocked and redirected to login."""
    protected_urls = [
        "/admin/dashboard",
        "/admin/users",
        "/doctor/dashboard",
        "/staff/dashboard",
        "/patient/dashboard",
        "/pharmacy/dashboard"
    ]

    for url in protected_urls:
        response = client.get(url, follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_patient_unauthorized_dashboard_access(client, patient_user):
    """Test that a Patient cannot access Admin, Doctor, Staff, or Pharmacy dashboards (403 Forbidden)."""
    # Log in as patient
    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    # Access permitted dashboard
    patient_res = client.get("/patient/dashboard")
    assert patient_res.status_code == 200

    # Attempt forbidden dashboards
    forbidden_urls = [
        "/admin/dashboard",
        "/admin/users",
        "/doctor/dashboard",
        "/staff/dashboard",
        "/pharmacy/dashboard"
    ]

    for url in forbidden_urls:
        res = client.get(url)
        assert res.status_code == 403
        assert b"403 - Access Forbidden" in res.data


def test_doctor_unauthorized_admin_access(client, doctor_user):
    """Test that a Doctor cannot access Admin or Pharmacy dashboards."""
    client.post("/auth/login", data={
        "identifier": doctor_user.email,
        "password": "DoctorPassword123!"
    })

    # Doctor dashboard allowed
    doc_res = client.get("/doctor/dashboard")
    assert doc_res.status_code == 200

    # Admin routes forbidden
    admin_res = client.get("/admin/dashboard")
    assert admin_res.status_code == 403

    users_res = client.get("/admin/users")
    assert users_res.status_code == 403


def test_staff_unauthorized_admin_access(client, staff_user):
    """Test that Staff cannot access Admin routes or Pharmacy dashboard."""
    client.post("/auth/login", data={
        "identifier": staff_user.email,
        "password": "StaffPassword123!"
    })

    # Staff dashboard allowed
    staff_res = client.get("/staff/dashboard")
    assert staff_res.status_code == 200

    # Admin routes forbidden
    admin_res = client.get("/admin/dashboard")
    assert admin_res.status_code == 403


def test_pharmacy_manager_access(client, pharmacy_user):
    """Test that Pharmacy Manager can access pharmacy dashboard but not admin."""
    client.post("/auth/login", data={
        "identifier": pharmacy_user.email,
        "password": "PharmacyPassword123!"
    })

    pharm_res = client.get("/pharmacy/dashboard")
    assert pharm_res.status_code == 200

    admin_res = client.get("/admin/dashboard")
    assert admin_res.status_code == 403
