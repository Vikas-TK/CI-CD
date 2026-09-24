from datetime import date, datetime, time
from sqlalchemy import or_
from app import db
from app.models.user import Role
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment, AppointmentStatus


class AppointmentService:
    """Service class encapsulating Appointment business logic, validation, and scheduling."""

    @classmethod
    def parse_date(cls, date_input):
        """Parses a date string (YYYY-MM-DD) or returns date instance."""
        if isinstance(date_input, date):
            return date_input, None
        if not date_input or not isinstance(date_input, str):
            return None, "Appointment date is required."
        try:
            parsed = datetime.strptime(date_input.strip(), "%Y-%m-%d").date()
            return parsed, None
        except ValueError:
            return None, "Invalid date format. Use YYYY-MM-DD."

    @classmethod
    def parse_time(cls, time_input):
        """Parses a time string (HH:MM) or returns time instance."""
        if isinstance(time_input, time):
            return time_input, None
        if not time_input or not isinstance(time_input, str):
            return None, "Appointment time is required."
        time_str = time_input.strip()
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
            try:
                parsed = datetime.strptime(time_str, fmt).time()
                return parsed, None
            except ValueError:
                continue
        return None, "Invalid time format. Use HH:MM (24-hour)."

    @classmethod
    def _validate_participants(cls, patient_id, doctor_id):
        """Validates patient and doctor existence and active status."""
        errors = []
        patient = Patient.query.get(patient_id) if patient_id else None
        if not patient:
            errors.append("Invalid or non-existent patient.")
        elif not patient.user or not patient.user.is_active:
            errors.append("Patient account is inactive.")

        doctor = Doctor.query.get(doctor_id) if doctor_id else None
        if not doctor:
            errors.append("Invalid or non-existent doctor.")
        elif not doctor.user or not doctor.user.is_active:
            errors.append("Doctor account is inactive or unavailable.")

        return errors, patient, doctor

    @classmethod
    def check_doctor_conflict(cls, doctor_id, appt_date, appt_time, exclude_id=None):
        """
        Checks if the doctor already has a PENDING or APPROVED appointment
        at the specified date and time.
        """
        query = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appt_date,
            Appointment.appointment_time == appt_time,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED])
        )
        if exclude_id:
            query = query.filter(Appointment.appointment_id != exclude_id)
        return query.first() is not None

    @classmethod
    def validate_appointment_data(cls, patient_id, doctor_id, date_input, time_input, reason_for_visit, exclude_id=None):
        """Validates all appointment booking attributes."""
        errors, _, doctor = cls._validate_participants(patient_id, doctor_id)

        parsed_date, date_err = cls.parse_date(date_input)
        if date_err:
            errors.append(date_err)
        elif parsed_date < date.today():
            errors.append("Appointment date cannot be in the past.")

        parsed_time, time_err = cls.parse_time(time_input)
        if time_err:
            errors.append(time_err)

        if not reason_for_visit or not reason_for_visit.strip():
            errors.append("Reason for visit is required.")
        elif len(reason_for_visit.strip()) < 3:
            errors.append("Reason for visit must be at least 3 characters long.")
        elif len(reason_for_visit.strip()) > 1000:
            errors.append("Reason for visit cannot exceed 1000 characters.")

        if not errors and doctor and parsed_date and parsed_time:
            if cls.check_doctor_conflict(doctor_id, parsed_date, parsed_time, exclude_id=exclude_id):
                errors.append(
                    f"Dr. {doctor.full_name} is already booked at {parsed_time.strftime('%H:%M')} on "
                    f"{parsed_date.strftime('%Y-%m-%d')}. Please choose another time slot."
                )

        return errors, parsed_date, parsed_time

    @classmethod
    def create_appointment(cls, patient_id, doctor_id, date_input, time_input, reason_for_visit):
        """Creates and saves a new appointment in PENDING status."""
        errors, parsed_date, parsed_time = cls.validate_appointment_data(
            patient_id, doctor_id, date_input, time_input, reason_for_visit
        )
        if errors:
            return None, errors

        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_date=parsed_date,
            appointment_time=parsed_time,
            reason_for_visit=reason_for_visit.strip(),
            status=AppointmentStatus.PENDING
        )
        try:
            db.session.add(appointment)
            db.session.commit()
            return appointment, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Database error while booking appointment: {str(e)}"]

    @classmethod
    def get_appointment_by_id(cls, appointment_id):
        """Fetches appointment by primary key."""
        if not appointment_id:
            return None
        return Appointment.query.get(appointment_id)

    @classmethod
    def get_patient_appointments(cls, patient_id, status=None):
        """Returns all appointments belonging to a given patient."""
        query = Appointment.query.filter_by(patient_id=patient_id)
        if status and AppointmentStatus.is_valid(status):
            query = query.filter_by(status=status)
        return query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()

    @classmethod
    def get_doctor_appointments(cls, doctor_id, status=None, date_filter=None):
        """Returns all appointments assigned to a given doctor."""
        query = Appointment.query.filter_by(doctor_id=doctor_id)
        if status and AppointmentStatus.is_valid(status):
            query = query.filter_by(status=status)
        if date_filter:
            parsed_date, err = cls.parse_date(date_filter)
            if parsed_date and not err:
                query = query.filter_by(appointment_date=parsed_date)
        return query.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()

    @classmethod
    def get_all_appointments(cls, status=None, date_filter=None, doctor_id=None,
                             patient_id=None, search=None, page=1, per_page=15):
        """Hospital-wide appointment query with filtering, search, and pagination."""
        query = Appointment.query.join(Patient, Appointment.patient_id == Patient.patient_id)\
                                 .join(Doctor, Appointment.doctor_id == Doctor.doctor_id)

        if status and AppointmentStatus.is_valid(status):
            query = query.filter(Appointment.status == status)

        if date_filter:
            parsed_date, err = cls.parse_date(date_filter)
            if parsed_date and not err:
                query = query.filter(Appointment.appointment_date == parsed_date)

        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)

        if patient_id:
            query = query.filter(Appointment.patient_id == patient_id)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Patient.full_name.ilike(term),
                    Doctor.full_name.ilike(term),
                    Doctor.specialization.ilike(term),
                    Appointment.reason_for_visit.ilike(term)
                )
            )

        return query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())\
                    .paginate(page=page, per_page=per_page, error_out=False)

    @classmethod
    def _validate_patient_transition(cls, user, appointment, new_status, current_status):
        patient = Patient.query.filter_by(user_id=user.user_id).first()
        if not patient or appointment.patient_id != patient.patient_id:
            return ["You are not authorized to modify this appointment."]
        if new_status != AppointmentStatus.CANCELLED:
            return ["Patients are only permitted to cancel their own appointments."]
        if current_status not in [AppointmentStatus.PENDING, AppointmentStatus.APPROVED]:
            return [f"Cannot cancel appointment with status {current_status}."]
        return []

    @classmethod
    def _validate_doctor_transition(cls, user, appointment, new_status, current_status):
        doctor = Doctor.query.filter_by(user_id=user.user_id).first()
        if not doctor or appointment.doctor_id != doctor.doctor_id:
            return ["You can only update appointments scheduled with you."]
        if new_status not in [AppointmentStatus.APPROVED, AppointmentStatus.REJECTED, AppointmentStatus.COMPLETED]:
            return [f"Doctors cannot set status to {new_status}."]
        if current_status == AppointmentStatus.PENDING and new_status == AppointmentStatus.COMPLETED:
            return ["Cannot complete a pending appointment. It must first be approved."]
        return []

    @classmethod
    def _validate_role_transition(cls, user, appointment, new_status):
        """Validates RBAC and state machine constraints for status update."""
        if not AppointmentStatus.is_valid(new_status):
            return [f"Invalid status value: {new_status}."]

        current_status = appointment.status
        if current_status in [AppointmentStatus.REJECTED, AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]:
            return [f"Cannot modify an appointment that is already {current_status}."]

        if user.role == Role.PATIENT:
            return cls._validate_patient_transition(user, appointment, new_status, current_status)
        elif user.role == Role.DOCTOR:
            return cls._validate_doctor_transition(user, appointment, new_status, current_status)
        elif user.role in [Role.STAFF, Role.ADMINISTRATOR]:
            if current_status == AppointmentStatus.PENDING and new_status == AppointmentStatus.COMPLETED:
                return ["Cannot complete a pending appointment. It must first be approved."]
            return []
        return ["Unauthorized role for appointment management."]

    @classmethod
    def update_appointment_status(cls, appointment_id, new_status, user, review_notes=None):
        """Transitions appointment status enforcing RBAC and state machine rules."""
        appointment = cls.get_appointment_by_id(appointment_id)
        if not appointment:
            return None, ["Appointment not found."]

        errors = cls._validate_role_transition(user, appointment, new_status)
        if errors:
            return None, errors

        # Double-booking check when approving
        if new_status == AppointmentStatus.APPROVED:
            conflict = Appointment.query.filter(
                Appointment.doctor_id == appointment.doctor_id,
                Appointment.appointment_date == appointment.appointment_date,
                Appointment.appointment_time == appointment.appointment_time,
                Appointment.status == AppointmentStatus.APPROVED,
                Appointment.appointment_id != appointment.appointment_id
            ).first()
            if conflict:
                return None, [
                    f"Cannot approve: Dr. {appointment.doctor_name} already has an approved appointment "
                    f"at this date and time."
                ]

        appointment.status = new_status
        if review_notes is not None:
            appointment.review_notes = review_notes.strip() if review_notes.strip() else None

        try:
            db.session.commit()
            return appointment, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Database error updating appointment status: {str(e)}"]

    @classmethod
    def get_patient_appointment_stats(cls, patient_id):
        """Returns count statistics for a patient's appointments."""
        base = Appointment.query.filter_by(patient_id=patient_id)
        return {
            "total": base.count(),
            "pending": base.filter_by(status=AppointmentStatus.PENDING).count(),
            "approved": base.filter_by(status=AppointmentStatus.APPROVED).count(),
            "completed": base.filter_by(status=AppointmentStatus.COMPLETED).count(),
            "cancelled": base.filter_by(status=AppointmentStatus.CANCELLED).count(),
            "rejected": base.filter_by(status=AppointmentStatus.REJECTED).count()
        }

    @classmethod
    def get_doctor_appointment_stats(cls, doctor_id):
        """Returns count statistics for a doctor's appointments."""
        base = Appointment.query.filter_by(doctor_id=doctor_id)
        today = date.today()
        return {
            "total": base.count(),
            "today": base.filter_by(appointment_date=today).count(),
            "pending": base.filter_by(status=AppointmentStatus.PENDING).count(),
            "approved": base.filter_by(status=AppointmentStatus.APPROVED).count(),
            "completed": base.filter_by(status=AppointmentStatus.COMPLETED).count(),
            "cancelled": base.filter_by(status=AppointmentStatus.CANCELLED).count(),
            "rejected": base.filter_by(status=AppointmentStatus.REJECTED).count()
        }

    @classmethod
    def get_hospital_appointment_stats(cls):
        """Returns count statistics for hospital-wide appointments."""
        today = date.today()
        return {
            "total": Appointment.query.count(),
            "today": Appointment.query.filter_by(appointment_date=today).count(),
            "pending": Appointment.query.filter_by(status=AppointmentStatus.PENDING).count(),
            "approved": Appointment.query.filter_by(status=AppointmentStatus.APPROVED).count(),
            "completed": Appointment.query.filter_by(status=AppointmentStatus.COMPLETED).count(),
            "cancelled": Appointment.query.filter_by(status=AppointmentStatus.CANCELLED).count(),
            "rejected": Appointment.query.filter_by(status=AppointmentStatus.REJECTED).count()
        }
