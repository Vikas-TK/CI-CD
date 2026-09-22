import re
from sqlalchemy import or_
from app import db
from app.models.user import User, Role
from app.models.doctor import Doctor
from app.services.user_service import UserService


class DoctorService:
    """Service class encapsulating Doctor profile management, validation, and search logic."""

    VALID_SPECIALIZATIONS = [
        "General Physician",
        "Cardiologist",
        "Dermatologist",
        "ENT Specialist",
        "Ophthalmologist",
        "Orthopedic Specialist",
        "Pediatrician",
        "Neurologist",
        "Gynecologist",
        "Psychiatrist",
        "General Surgeon",
        "Radiologist",
        "Oncologist",
        "Urologist",
        "Endocrinologist",
        "Anesthesiologist",
        "Pathologist",
        "Gastroenterologist",
        "Nephrologist",
        "Pulmonologist"
    ]

    @classmethod
    def validate_specialization(cls, specialization):
        """Validates doctor medical specialization."""
        if not specialization or not specialization.strip():
            return ["Doctor specialization is required."]

        spec = specialization.strip()
        if len(spec) < 2 or len(spec) > 100:
            return ["Specialization must be between 2 and 100 characters."]

        # Ensure alphanumeric characters, spaces, hyphens, and slashes
        pattern = re.compile(r"^[a-zA-Z\s\-/&.,()]+$")
        if not pattern.match(spec):
            return ["Specialization contains invalid characters."]

        return []

    @classmethod
    def _validate_phone(cls, phone_number):
        """Validates phone number format."""
        if not phone_number or not phone_number.strip():
            return "Phone number is required."
        phone_pattern = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
        if not phone_pattern.match(phone_number.strip()):
            return "Invalid phone number format. Provide 7 to 15 digits."
        return None

    @classmethod
    def get_doctor_by_id(cls, doctor_id):

        """Fetches doctor profile by primary key doctor_id."""
        return db.session.get(Doctor, int(doctor_id))

    @classmethod
    def get_doctor_by_user_id(cls, user_id):
        """Fetches doctor profile linked to given user_id."""
        return Doctor.query.filter_by(user_id=int(user_id)).first()

    @classmethod
    def create_doctor_profile(cls, user_id, specialization):
        """
        Creates and associates a doctor profile with an existing user account with DOCTOR role.
        """
        user = db.session.get(User, int(user_id)) if user_id else None

        if not user:
            return None, ["Specified user account does not exist."]

        if user.role != Role.DOCTOR:
            return None, ["Cannot link doctor profile to a non-doctor account."]

        existing_profile = cls.get_doctor_by_user_id(user_id)
        if existing_profile:
            return None, ["Doctor profile already exists for this user account."]

        spec_errors = cls.validate_specialization(specialization)
        if spec_errors:
            return None, spec_errors

        try:
            doctor = Doctor(
                user_id=user.user_id,
                specialization=specialization.strip()
            )
            db.session.add(doctor)
            db.session.commit()
            return doctor, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while creating the doctor profile."]

    @classmethod
    def create_doctor_with_account(cls, first_name, last_name, email, phone_number,
                                   password, specialization, is_active=True):
        """
        Administrator workflow to create a DOCTOR user and their Doctor profile atomically.
        """
        spec_errors = cls.validate_specialization(specialization)
        if spec_errors:
            return None, spec_errors

        user, user_errors = UserService.create_privileged_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            password=password,
            role=Role.DOCTOR,
            is_active=is_active
        )

        if user_errors:
            return None, user_errors

        doctor, doc_errors = cls.create_doctor_profile(
            user_id=user.user_id,
            specialization=specialization
        )

        if doc_errors:
            db.session.delete(user)
            db.session.commit()
            return None, doc_errors

        return doctor, []

    @classmethod
    def _is_update_authorized(cls, updating_user, doctor):
        """Checks if current user has permission to update the doctor profile."""
        if not updating_user or not updating_user.is_authenticated:
            return False
        if updating_user.is_admin:
            return True
        return updating_user.is_doctor and doctor.user_id == updating_user.user_id

    @classmethod
    def _apply_phone_update(cls, doctor, phone_number, errors):
        """Applies phone number updates and duplicate checks."""
        phone_val = phone_number.strip()
        phone_err = cls._validate_phone(phone_val)
        if phone_err:
            errors.append(phone_err)
            return

        existing_phone = User.query.filter(
            User.phone_number == phone_val,
            User.user_id != doctor.user_id
        ).first()
        if existing_phone:
            errors.append("This phone number is already registered by another account.")
        else:
            doctor.user.phone_number = phone_val

    @classmethod
    def update_doctor_profile(cls, doctor_id, updating_user, specialization=None, phone_number=None):
        """
        Updates doctor profile fields with strict role authorization.
        """
        doctor = cls.get_doctor_by_id(doctor_id)
        if not doctor:
            return None, ["Doctor profile not found."]

        if not cls._is_update_authorized(updating_user, doctor):
            return None, ["Unauthorized: You do not have permission to update this doctor profile."]

        errors = []
        if specialization is not None and specialization.strip():
            spec_errors = cls.validate_specialization(specialization)
            if spec_errors:
                errors.extend(spec_errors)
            else:
                doctor.specialization = specialization.strip()

        if phone_number is not None and phone_number.strip():
            cls._apply_phone_update(doctor, phone_number, errors)

        if errors:
            return None, errors

        try:
            db.session.commit()
            return doctor, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while updating the doctor profile."]

    @classmethod
    def list_doctors(cls, search_query=None, specialization_filter=None, status_filter=None):

        """
        Retrieves doctor profiles query with optional search, specialization, and status filtering.
        """
        query = Doctor.query.join(User, Doctor.user_id == User.user_id)

        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            conditions = [
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
                User.phone_number.ilike(term),
                Doctor.specialization.ilike(term)
            ]
            if search_query.strip().isdigit():
                conditions.append(Doctor.doctor_id == int(search_query.strip()))
            query = query.filter(or_(*conditions))

        if specialization_filter and specialization_filter.strip():
            query = query.filter(Doctor.specialization.ilike(f"%{specialization_filter.strip()}%"))

        if status_filter and status_filter.strip():
            if status_filter.lower() == "active":
                query = query.filter(User.is_active.is_(True))
            elif status_filter.lower() == "inactive":
                query = query.filter(User.is_active.is_(False))

        return query.order_by(Doctor.doctor_id.asc())

    @classmethod
    def get_unprofiled_doctor_users(cls):
        """Returns doctor accounts that do not have a doctor profile record yet."""
        profiled_user_ids = db.session.query(Doctor.user_id)
        return User.query.filter(
            User.role == Role.DOCTOR,
            ~User.user_id.in_(profiled_user_ids)
        ).all()
