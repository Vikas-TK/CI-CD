import pytest
from app.models.user import User, Role


def test_landing_page(client):
    """Test public landing page is accessible."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"MediCare HMS" in response.data
    assert b"Modern, Secure Hospital Operations" in response.data


def test_health_check_endpoint(client):
    """Test health check returns HTTP 200 and healthy JSON payload."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"
    assert "version" in json_data


def test_patient_registration_success(client):
    """Test successful patient self-registration with automatic PATIENT role assignment."""
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "phone_number": "+15550198888",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    }
    response = client.post("/auth/register", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful" in response.data

    # Verify user in database
    user = User.query.filter_by(email="jane.doe@example.com").first()
    assert user is not None
    assert user.first_name == "Jane"
    assert user.last_name == "Doe"
    assert user.role == Role.PATIENT
    assert user.is_active is True
    assert user.check_password("SecurePassword123!") is True
    assert user.password_hash != "SecurePassword123!"  # Passwords must be securely hashed


def test_patient_registration_password_mismatch(client):
    """Test registration failure when passwords do not match."""
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.mismatch@example.com",
        "phone_number": "+15550198889",
        "password": "SecurePassword123!",
        "confirm_password": "DifferentPassword123!"
    }
    response = client.post("/auth/register", data=payload)
    assert response.status_code == 400
    assert b"Passwords do not match" in response.data
    assert User.query.filter_by(email="jane.mismatch@example.com").first() is None


def test_patient_registration_short_password(client):
    """Test registration failure when password is too short (< 6 chars)."""
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.short@example.com",
        "phone_number": "+15550198890",
        "password": "123",
        "confirm_password": "123"
    }
    response = client.post("/auth/register", data=payload)
    assert response.status_code == 400
    assert b"Password must be at least 6 characters long" in response.data


def test_patient_registration_duplicate_email(client, patient_user):
    """Test registration failure on duplicate email."""
    payload = {
        "first_name": "Another",
        "last_name": "User",
        "email": patient_user.email,
        "phone_number": "+1999999999",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    response = client.post("/auth/register", data=payload)
    assert response.status_code == 400
    assert b"An account with this email address already exists" in response.data


def test_patient_registration_duplicate_phone(client, patient_user):
    """Test registration failure on duplicate phone number."""
    payload = {
        "first_name": "Another",
        "last_name": "User",
        "email": "unique.email@example.com",
        "phone_number": patient_user.phone_number,
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    response = client.post("/auth/register", data=payload)
    assert response.status_code == 400
    assert b"An account with this phone number already exists" in response.data


def test_login_with_email_success(client, patient_user):
    """Test successful user login using email identifier."""
    response = client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Patient Portal" in response.data


def test_login_with_phone_success(client, patient_user):
    """Test successful user login using phone number identifier."""
    response = client.post("/auth/login", data={
        "identifier": patient_user.phone_number,
        "password": "PatientPassword123!"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Patient Portal" in response.data


def test_login_invalid_password(client, patient_user):
    """Test login failure with invalid password."""
    response = client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "WrongPassword!"
    })
    assert response.status_code == 401
    assert b"Invalid email/phone number or password" in response.data


def test_login_inactive_user(client, inactive_user):
    """Test login rejection for deactivated user accounts."""
    response = client.post("/auth/login", data={
        "identifier": inactive_user.email,
        "password": "InactivePassword123!"
    })
    assert response.status_code == 401
    assert b"account is deactivated" in response.data


def test_logout_functionality(client, patient_user):
    """Test logout ends authenticated session."""
    # Login first
    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    # Logout
    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"successfully logged out" in response.data

    # Attempting to access dashboard should now redirect to login
    dash_response = client.get("/patient/dashboard", follow_redirects=False)
    assert dash_response.status_code == 302
    assert "/auth/login" in dash_response.location
