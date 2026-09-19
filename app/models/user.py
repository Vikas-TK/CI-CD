from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Role:
    """Standardized Role constants for Hospital Management System."""
    ADMINISTRATOR = "ADMINISTRATOR"
    DOCTOR = "DOCTOR"
    STAFF = "STAFF"
    PATIENT = "PATIENT"
    PHARMACY_MANAGER = "PHARMACY_MANAGER"

    ALL_ROLES = [ADMINISTRATOR, DOCTOR, STAFF, PATIENT, PHARMACY_MANAGER]
    PRIVILEGED_ROLES = [ADMINISTRATOR, DOCTOR, STAFF, PHARMACY_MANAGER]

    @classmethod
    def is_valid(cls, role_name):
        return role_name in cls.ALL_ROLES

    @classmethod
    def get_dashboard_route(cls, role_name):
        routes = {
            cls.ADMINISTRATOR: "admin.dashboard",
            cls.DOCTOR: "doctor.dashboard",
            cls.STAFF: "staff.dashboard",
            cls.PATIENT: "patient.dashboard",
            cls.PHARMACY_MANAGER: "pharmacy.dashboard"
        }
        return routes.get(role_name, "main.index")


class User(UserMixin, db.Model):
    """
    User entity representing system credentials and authentication metadata.
    Decoupled from domain-specific profiles (Patients, Doctors, Staff, etc.).
    """
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default=Role.PATIENT, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, first_name, last_name, email, phone_number, password=None, role=Role.PATIENT, is_active=True):
        self.first_name = first_name.strip()
        self.last_name = last_name.strip()
        self.email = email.strip().lower()
        self.phone_number = phone_number.strip()
        self.role = role if Role.is_valid(role) else Role.PATIENT
        self.is_active = is_active
        if password:
            self.set_password(password)

    def set_password(self, password):
        """Hashes the password securely using Werkzeug."""
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        """Verifies the password against the stored secure hash."""
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """Flask-Login requires user ID as string."""
        return str(self.user_id)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self):
        return self.role == Role.ADMINISTRATOR

    @property
    def is_doctor(self):
        return self.role == Role.DOCTOR

    @property
    def is_staff(self):
        return self.role == Role.STAFF

    @property
    def is_patient(self):
        return self.role == Role.PATIENT

    @property
    def is_pharmacy_manager(self):
        return self.role == Role.PHARMACY_MANAGER

    def to_dict(self):
        """Serialize user model to dictionary for API responses (excluding password hash)."""
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<User user_id={self.user_id} email='{self.email}' role='{self.role}' active={self.is_active}>"
