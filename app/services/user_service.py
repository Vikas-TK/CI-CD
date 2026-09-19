import re
from email_validator import validate_email, EmailNotValidError
from sqlalchemy import or_
from app import db
from app.models.user import User, Role


class UserService:
    """Service class encapsulating authentication, user management, and authorization business logic."""

    @staticmethod
    def validate_name(first_name, last_name):
        """Validates first and last name fields."""
        errors = []
        if not first_name or not first_name.strip():
            errors.append("First name is required.")
        elif len(first_name.strip()) < 2 or len(first_name.strip()) > 50:
            errors.append("First name must be between 2 and 50 characters.")

        if not last_name or not last_name.strip():
            errors.append("Last name is required.")
        elif len(last_name.strip()) < 2 or len(last_name.strip()) > 50:
            errors.append("Last name must be between 2 and 50 characters.")
        return errors

    @staticmethod
    def validate_contact(email, phone_number):
        """Validates email format and phone number structure."""
        errors = []
        if not email or not email.strip():
            errors.append("Email address is required.")
        else:
            try:
                validate_email(email.strip(), check_deliverability=False, test_environment=True)
            except EmailNotValidError as e:
                errors.append(f"Invalid email address: {str(e)}")

        if not phone_number or not phone_number.strip():
            errors.append("Phone number is required.")
        else:
            phone_pattern = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
            if not phone_pattern.match(phone_number.strip()):
                errors.append("Invalid phone number format. Provide 7 to 15 digits.")
        return errors

    @staticmethod
    def validate_password_match(password, confirm_password):
        """Validates password length and match."""
        errors = []
        if password is not None:
            if len(password) < 6:
                errors.append("Password must be at least 6 characters long.")
            if confirm_password is not None and password != confirm_password:
                errors.append("Passwords do not match.")
        return errors

    @classmethod
    def validate_user_input(cls, first_name, last_name, email, phone_number, password=None, confirm_password=None):
        """Validates user attributes and returns a list of error messages (empty if valid)."""
        errors = []
        errors.extend(cls.validate_name(first_name, last_name))
        errors.extend(cls.validate_contact(email, phone_number))
        errors.extend(cls.validate_password_match(password, confirm_password))
        return errors

    @classmethod
    def register_patient(cls, first_name, last_name, email, phone_number, password, confirm_password):
        """
        Public patient registration. Strictly enforces the PATIENT role.
        """
        errors = cls.validate_user_input(
            first_name, last_name, email, phone_number, password, confirm_password
        )
        if errors:
            return None, errors

        email = email.strip().lower()
        phone_number = phone_number.strip()

        # Check for uniqueness
        if User.query.filter_by(email=email).first():
            return None, ["An account with this email address already exists."]

        if User.query.filter_by(phone_number=phone_number).first():
            return None, ["An account with this phone number already exists."]

        try:
            new_patient = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                password=password,
                role=Role.PATIENT,
                is_active=True
            )
            db.session.add(new_patient)
            db.session.commit()
            return new_patient, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Registration failed: {str(e)}"]

    @classmethod
    def authenticate(cls, identifier, password):
        """
        Authenticates user by email or phone number.
        Returns (user, error_message).
        """
        if not identifier or not password:
            return None, "Please provide both your login identifier and password."

        identifier_clean = identifier.strip().lower()

        # Match either email or phone_number
        user = User.query.filter(
            or_(
                User.email == identifier_clean,
                User.phone_number == identifier.strip()
            )
        ).first()

        if not user or not user.check_password(password):
            return None, "Invalid email/phone number or password."

        if not user.is_active:
            return None, "Your account is deactivated. Please contact the hospital administrator."

        return user, None

    @classmethod
    def create_privileged_user(cls, first_name, last_name, email, phone_number, password, role, is_active=True):
        """
        Creates a privileged account (Administrator, Doctor, Staff, Pharmacy Manager).
        """
        if role not in Role.ALL_ROLES:
            return None, [f"Invalid role: {role}."]

        errors = cls.validate_user_input(first_name, last_name, email, phone_number, password, password)
        if errors:
            return None, errors

        email = email.strip().lower()
        phone_number = phone_number.strip()

        if User.query.filter_by(email=email).first():
            return None, ["An account with this email address already exists."]

        if User.query.filter_by(phone_number=phone_number).first():
            return None, ["An account with this phone number already exists."]

        try:
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                password=password,
                role=role,
                is_active=is_active
            )
            db.session.add(user)
            db.session.commit()
            return user, []
        except Exception as e:
            db.session.rollback()
            return None, [f"User creation failed: {str(e)}"]

    @classmethod
    def get_users(cls, search_query=None, role_filter=None, status_filter=None):
        """Returns filtered user query."""
        query = User.query

        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                    User.email.ilike(term),
                    User.phone_number.ilike(term)
                )
            )

        if role_filter and Role.is_valid(role_filter):
            query = query.filter_by(role=role_filter)

        if status_filter is not None and status_filter != "":
            if status_filter in ["active", "1", True]:
                query = query.filter_by(is_active=True)
            elif status_filter in ["inactive", "0", False]:
                query = query.filter_by(is_active=False)

        return query.order_by(User.created_at.desc())

    @classmethod
    def toggle_user_status(cls, target_user_id, current_admin_user_id):
        """
        Toggles is_active between True and False.
        Guards against deactivating the current administrator.
        """
        if int(target_user_id) == int(current_admin_user_id):
            return False, "You cannot deactivate your own administrator account."

        user = db.session.get(User, int(target_user_id))
        if not user:
            return False, "User not found."

        try:
            user.is_active = not user.is_active
            db.session.commit()
            status_str = "activated" if user.is_active else "deactivated"
            return True, f"User {user.email} successfully {status_str}."
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to update status: {str(e)}"

    @classmethod
    def update_user_role(cls, target_user_id, new_role, current_admin_user_id):
        """Updates a user's role safely."""
        if not Role.is_valid(new_role):
            return False, f"Invalid role: {new_role}."

        if int(target_user_id) == int(current_admin_user_id) and new_role != Role.ADMINISTRATOR:
            admin_count = User.query.filter_by(role=Role.ADMINISTRATOR, is_active=True).count()
            if admin_count <= 1:
                return False, "Cannot demote the only active Administrator account."

        user = db.session.get(User, int(target_user_id))
        if not user:
            return False, "User not found."

        try:
            user.role = new_role
            db.session.commit()
            return True, f"User {user.email} role updated to {new_role}."
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to update role: {str(e)}"
