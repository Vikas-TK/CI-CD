import re
from sqlalchemy import or_
from app import db
from app.models.user import User, Role
from app.models.staff import Staff
from app.services.user_service import UserService


class StaffService:
    """Service class encapsulating Staff profile management, validation, and search logic."""

    VALID_DESIGNATIONS = [
        "Nurse",
        "Receptionist",
        "Lab Technician",
        "Pharmacist Assistant",
        "Ward Assistant",
        "Accountant",
        "Administrative Staff",
        "Other"
    ]

    @classmethod
    def validate_designation(cls, designation):
        """Validates staff job designation."""
        if not designation or not designation.strip():
            return ["Staff designation is required."]

        desig = designation.strip()
        if len(desig) < 2 or len(desig) > 100:
            return ["Designation must be between 2 and 100 characters."]

        pattern = re.compile(r"^[a-zA-Z0-9\s\-/&.,()]+$")
        if not pattern.match(desig):
            return ["Designation contains invalid characters."]

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
    def _validate_aadhaar(cls, aadhaar_number):
        """Validates 12-digit Indian Aadhaar number format if provided."""
        if not aadhaar_number or not aadhaar_number.strip():
            return None
        clean_aadhaar = aadhaar_number.strip().replace(" ", "").replace("-", "")
        if not clean_aadhaar.isdigit() or len(clean_aadhaar) != 12:
            return "Aadhaar number must be exactly 12 numeric digits."
        return None

    @classmethod
    def get_staff_by_id(cls, staff_id):
        """Fetches staff profile by primary key staff_id."""
        return db.session.get(Staff, int(staff_id))

    @classmethod
    def get_staff_by_user_id(cls, user_id):
        """Fetches staff profile linked to given user_id."""
        return Staff.query.filter_by(user_id=int(user_id)).first()

    @classmethod
    def create_staff_profile(cls, user_id, designation, aadhaar_number=None):
        """
        Creates and associates a staff profile with an existing user account with STAFF role.
        """
        user = db.session.get(User, int(user_id)) if user_id else None

        if not user:
            return None, ["Specified user account does not exist."]

        if user.role != Role.STAFF:
            return None, ["Cannot link staff profile to a non-staff account."]

        existing_profile = cls.get_staff_by_user_id(user_id)
        if existing_profile:
            return None, ["Staff profile already exists for this user account."]

        errors = cls.validate_designation(designation)
        aadhaar_err = cls._validate_aadhaar(aadhaar_number)
        if aadhaar_err:
            errors.append(aadhaar_err)

        if errors:
            return None, errors

        try:
            staff = Staff(
                user_id=user.user_id,
                designation=designation.strip(),
                aadhaar_number=aadhaar_number
            )
            db.session.add(staff)
            db.session.commit()
            return staff, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while creating the staff profile."]

    @classmethod
    def create_staff_with_account(cls, first_name, last_name, email, phone_number,
                                  password, designation, aadhaar_number=None, is_active=True):
        """
        Administrator workflow to create a STAFF user and their Staff profile atomically.
        """
        errors = cls.validate_designation(designation)
        aadhaar_err = cls._validate_aadhaar(aadhaar_number)
        if aadhaar_err:
            errors.append(aadhaar_err)

        if errors:
            return None, errors

        user, user_errors = UserService.create_privileged_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            password=password,
            role=Role.STAFF,
            is_active=is_active
        )

        if user_errors:
            return None, user_errors

        staff, staff_errors = cls.create_staff_profile(
            user_id=user.user_id,
            designation=designation,
            aadhaar_number=aadhaar_number
        )

        if staff_errors:
            db.session.delete(user)
            db.session.commit()
            return None, staff_errors

        return staff, []

    @classmethod
    def _is_update_authorized(cls, updating_user, staff):
        """Checks if current user has permission to update the staff profile."""
        if not updating_user or not updating_user.is_authenticated:
            return False
        if updating_user.is_admin:
            return True
        return updating_user.is_staff and staff.user_id == updating_user.user_id

    @classmethod
    def _apply_phone_update(cls, staff, phone_number, errors):
        """Applies phone number updates and duplicate checks."""
        phone_val = phone_number.strip()
        phone_err = cls._validate_phone(phone_val)
        if phone_err:
            errors.append(phone_err)
            return

        existing_phone = User.query.filter(
            User.phone_number == phone_val,
            User.user_id != staff.user_id
        ).first()
        if existing_phone:
            errors.append("This phone number is already registered by another account.")
        else:
            staff.user.phone_number = phone_val

    @classmethod
    def _apply_aadhaar_update(cls, staff, aadhaar_number, errors):
        """Applies Aadhaar number updates with format validation."""
        if not aadhaar_number or not aadhaar_number.strip():
            staff.aadhaar_number = None
            return
        clean_aadhaar = aadhaar_number.strip().replace(" ", "").replace("-", "")
        aadhaar_err = cls._validate_aadhaar(clean_aadhaar)
        if aadhaar_err:
            errors.append(aadhaar_err)
        else:
            staff.aadhaar_number = clean_aadhaar

    @classmethod
    def _apply_designation_update(cls, staff, designation, updating_user, errors):
        """Applies designation updates with admin authorization check."""
        if not updating_user.is_admin:
            errors.append("Only administrators can update staff designation.")
            return

        desig_errors = cls.validate_designation(designation)
        if desig_errors:
            errors.extend(desig_errors)
        else:
            staff.designation = designation.strip()

    @classmethod
    def update_staff_profile(cls, staff_id, updating_user, designation=None, phone_number=None, aadhaar_number=None):
        """
        Updates staff profile fields with strict role authorization.
        """
        staff = cls.get_staff_by_id(staff_id)
        if not staff:
            return None, ["Staff profile not found."]

        if not cls._is_update_authorized(updating_user, staff):
            return None, ["Unauthorized: You do not have permission to update this staff profile."]

        errors = []

        if designation is not None and designation.strip():
            cls._apply_designation_update(staff, designation, updating_user, errors)

        if phone_number is not None and phone_number.strip():
            cls._apply_phone_update(staff, phone_number, errors)

        if aadhaar_number is not None:
            cls._apply_aadhaar_update(staff, aadhaar_number, errors)

        if errors:
            return None, errors

        try:
            db.session.commit()
            return staff, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while updating the staff profile."]

    @classmethod
    def list_staff(cls, search_query=None, designation_filter=None, status_filter=None):
        """
        Retrieves staff profiles query with optional search, designation, and status filtering.
        """
        query = Staff.query.join(User, Staff.user_id == User.user_id)

        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            conditions = [
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
                User.phone_number.ilike(term),
                Staff.designation.ilike(term)
            ]
            if search_query.strip().isdigit():
                conditions.append(Staff.staff_id == int(search_query.strip()))
            query = query.filter(or_(*conditions))

        if designation_filter and designation_filter.strip():
            query = query.filter(Staff.designation.ilike(f"%{designation_filter.strip()}%"))

        if status_filter and status_filter.strip():
            if status_filter.lower() == "active":
                query = query.filter(User.is_active.is_(True))
            elif status_filter.lower() == "inactive":
                query = query.filter(User.is_active.is_(False))

        return query.order_by(Staff.staff_id.asc())

    @classmethod
    def get_unprofiled_staff_users(cls):
        """Returns staff accounts that do not have a staff profile record yet."""
        profiled_user_ids = db.session.query(Staff.user_id)
        return User.query.filter(
            User.role == Role.STAFF,
            ~User.user_id.in_(profiled_user_ids)
        ).all()
