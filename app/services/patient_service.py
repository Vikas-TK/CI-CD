import re
from sqlalchemy import or_
from app import db
from app.models.user import User, Role
from app.models.patient import Patient


class PatientService:
    """Service class encapsulating Patient profile management, validation, and search logic."""

    VALID_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    VALID_GENDERS = ["Male", "Female", "Other", "Prefer not to say"]

    @classmethod
    def _validate_age(cls, age):
        if age is None or age == "":
            return None
        try:
            age_val = int(age)
            if age_val < 0 or age_val > 130:
                return "Age must be between 0 and 130 years."
        except (ValueError, TypeError):
            return "Age must be a valid whole number."
        return None

    @classmethod
    def _validate_aadhaar(cls, aadhaar_number):
        if not aadhaar_number or not aadhaar_number.strip():
            return None
        clean_aadhaar = aadhaar_number.strip().replace(" ", "").replace("-", "")
        if not clean_aadhaar.isdigit() or len(clean_aadhaar) != 12:
            return "Aadhaar number must be exactly 12 digits."
        return None

    @classmethod
    def validate_patient_data(cls, age=None, gender=None, aadhaar_number=None,
                              blood_group=None, emergency_contact_phone=None):
        """Validates patient domain fields."""
        errors = []

        age_err = cls._validate_age(age)
        if age_err:
            errors.append(age_err)

        if gender and gender not in cls.VALID_GENDERS:
            errors.append(f"Gender must be one of: {', '.join(cls.VALID_GENDERS)}.")

        if blood_group and blood_group not in cls.VALID_BLOOD_GROUPS:
            errors.append(f"Blood group must be one of: {', '.join(cls.VALID_BLOOD_GROUPS)}.")

        aadhaar_err = cls._validate_aadhaar(aadhaar_number)
        if aadhaar_err:
            errors.append(aadhaar_err)

        if emergency_contact_phone and emergency_contact_phone.strip():
            phone_pattern = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
            if not phone_pattern.match(emergency_contact_phone.strip()):
                errors.append("Invalid emergency contact phone number format.")

        return errors

    @classmethod
    def get_patient_by_id(cls, patient_id):
        """Fetches patient profile by primary key patient_id."""
        return db.session.get(Patient, int(patient_id))

    @classmethod
    def get_patient_by_user_id(cls, user_id):
        """Fetches patient profile linked to given user_id."""
        return Patient.query.filter_by(user_id=int(user_id)).first()

    @classmethod
    def create_patient_profile(cls, user_id, age=None, gender=None, aadhaar_number=None,
                               blood_group=None, disease_or_complaint=None,
                               emergency_contact_name=None, emergency_contact_phone=None,
                               address=None):
        """
        Creates a new patient profile for an authenticated user.
        Enforces 1-to-1 relationship and validates inputs.
        """
        user = db.session.get(User, int(user_id))
        if not user:
            return None, ["Associated user account not found."]

        if user.role != Role.PATIENT and user.role != Role.ADMINISTRATOR:
            return None, ["Patient profiles can only be created for Patient accounts."]

        # Check if profile already exists for this user
        existing_profile = cls.get_patient_by_user_id(user_id)
        if existing_profile:
            return None, ["A patient profile already exists for this user account."]

        errors = cls.validate_patient_data(
            age=age,
            gender=gender,
            aadhaar_number=aadhaar_number,
            blood_group=blood_group,
            emergency_contact_phone=emergency_contact_phone
        )
        if errors:
            return None, errors

        # Process age
        parsed_age = int(age) if age is not None and str(age).strip() != "" else None

        try:
            patient = Patient(
                user_id=user.user_id,
                age=parsed_age,
                gender=gender,
                aadhaar_number=aadhaar_number,
                blood_group=blood_group,
                disease_or_complaint=disease_or_complaint,
                emergency_contact_name=emergency_contact_name,
                emergency_contact_phone=emergency_contact_phone,
                address=address
            )
            db.session.add(patient)
            db.session.commit()
            return patient, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Failed to create patient profile: {str(e)}"]

    @classmethod
    def update_patient_profile(cls, patient_id, updating_user, age=None, gender=None,
                               aadhaar_number=None, blood_group=None, disease_or_complaint=None,
                               emergency_contact_name=None, emergency_contact_phone=None,
                               address=None, phone_number=None):
        """
        Updates an existing patient profile with role-based ownership authorization.
        """
        patient = cls.get_patient_by_id(patient_id)
        if not patient:
            return None, ["Patient profile not found."]

        # Authorization: Patients may only update their own profile
        if updating_user.role == Role.PATIENT and patient.user_id != updating_user.user_id:
            return None, ["Unauthorized: You can only update your own patient profile."]

        errors = cls.validate_patient_data(
            age=age,
            gender=gender,
            aadhaar_number=aadhaar_number,
            blood_group=blood_group,
            emergency_contact_phone=emergency_contact_phone
        )

        # Update contact phone on associated User if provided
        if phone_number and phone_number.strip() and phone_number.strip() != patient.phone_number:
            clean_phone = phone_number.strip()
            existing_user = User.query.filter_by(phone_number=clean_phone).first()
            if existing_user and existing_user.user_id != patient.user_id:
                errors.append("An account with this phone number already exists.")
            else:
                phone_pattern = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
                if not phone_pattern.match(clean_phone):
                    errors.append("Invalid phone number format.")
                else:
                    patient.user.phone_number = clean_phone

        if errors:
            return None, errors

        try:
            patient.age = int(age) if age is not None and str(age).strip() != "" else None
            patient.gender = gender.strip() if gender else None
            if aadhaar_number is not None and aadhaar_number.strip() != "":
                patient.aadhaar_number = aadhaar_number.strip().replace(" ", "").replace("-", "")
            patient.blood_group = blood_group.strip() if blood_group else None
            patient.disease_or_complaint = disease_or_complaint.strip() if disease_or_complaint else None
            patient.emergency_contact_name = emergency_contact_name.strip() if emergency_contact_name else None
            patient.emergency_contact_phone = emergency_contact_phone.strip() if emergency_contact_phone else None
            patient.address = address.strip() if address else None

            db.session.commit()
            return patient, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Failed to update patient profile: {str(e)}"]

    @classmethod
    def list_patients(cls, search_query=None):
        """
        Lists patients with optional search by patient_id, name, email, or phone.
        """
        query = Patient.query.join(User, Patient.user_id == User.user_id)

        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            # If search term is integer, match patient_id as well
            if search_query.strip().isdigit():
                query = query.filter(
                    or_(
                        Patient.patient_id == int(search_query.strip()),
                        User.first_name.ilike(term),
                        User.last_name.ilike(term),
                        User.email.ilike(term),
                        User.phone_number.ilike(term)
                    )
                )
            else:
                query = query.filter(
                    or_(
                        User.first_name.ilike(term),
                        User.last_name.ilike(term),
                        User.email.ilike(term),
                        User.phone_number.ilike(term),
                        Patient.disease_or_complaint.ilike(term)
                    )
                )

        return query.order_by(Patient.created_at.desc())
