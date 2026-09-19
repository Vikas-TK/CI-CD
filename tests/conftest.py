import pytest
from app import create_app, db
from app.models.user import Role
from app.services.user_service import UserService


@pytest.fixture
def app():
    """Creates a configured Flask application for testing."""
    test_app = create_app("testing")

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Provides a test client for simulating HTTP requests."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Provides a CLI runner for testing Flask click commands."""
    return app.test_cli_runner()


@pytest.fixture
def admin_user(app):
    """Creates an Administrator user in the test database."""
    user, _ = UserService.create_privileged_user(
        first_name="Admin",
        last_name="User",
        email="admin@hospital.org",
        phone_number="+1000000001",
        password="AdminPassword123!",
        role=Role.ADMINISTRATOR,
        is_active=True
    )
    return user


@pytest.fixture
def doctor_user(app):
    """Creates a Doctor user in the test database."""
    user, _ = UserService.create_privileged_user(
        first_name="Doctor",
        last_name="User",
        email="doctor@hospital.org",
        phone_number="+1000000002",
        password="DoctorPassword123!",
        role=Role.DOCTOR,
        is_active=True
    )
    return user


@pytest.fixture
def staff_user(app):
    """Creates a Staff user in the test database."""
    user, _ = UserService.create_privileged_user(
        first_name="Staff",
        last_name="User",
        email="staff@hospital.org",
        phone_number="+1000000003",
        password="StaffPassword123!",
        role=Role.STAFF,
        is_active=True
    )
    return user


@pytest.fixture
def patient_user(app):
    """Creates a Patient user in the test database."""
    user, _ = UserService.register_patient(
        first_name="Patient",
        last_name="User",
        email="patient@hospital.org",
        phone_number="+1000000004",
        password="PatientPassword123!",
        confirm_password="PatientPassword123!"
    )
    return user


@pytest.fixture
def pharmacy_user(app):
    """Creates a Pharmacy Manager user in the test database."""
    user, _ = UserService.create_privileged_user(
        first_name="Pharmacy",
        last_name="User",
        email="pharmacy@hospital.org",
        phone_number="+1000000005",
        password="PharmacyPassword123!",
        role=Role.PHARMACY_MANAGER,
        is_active=True
    )
    return user


@pytest.fixture
def inactive_user(app):
    """Creates an Inactive user in the test database."""
    user, _ = UserService.create_privileged_user(
        first_name="Inactive",
        last_name="User",
        email="inactive@hospital.org",
        phone_number="+1000000006",
        password="InactivePassword123!",
        role=Role.PATIENT,
        is_active=False
    )
    return user
