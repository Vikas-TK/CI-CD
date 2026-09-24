from datetime import datetime, timezone
from app import db


class AppointmentStatus:
    """Standard appointment lifecycle status constants."""
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"

    ALL_STATUSES = [PENDING, APPROVED, REJECTED, CANCELLED, COMPLETED]

    @classmethod
    def is_valid(cls, status):
        return status in cls.ALL_STATUSES


class Appointment(db.Model):
    """
    Appointment domain model representing clinical consultations scheduled between
    a patient and a doctor.
    """
    __tablename__ = "appointments"

    appointment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.doctor_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    appointment_time = db.Column(db.Time, nullable=False)
    reason_for_visit = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default=AppointmentStatus.PENDING,
        index=True
    )
    review_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    patient = db.relationship("Patient", backref=db.backref("appointments", cascade="all, delete-orphan", lazy="dynamic"))
    doctor = db.relationship("Doctor", backref=db.backref("appointments", cascade="all, delete-orphan", lazy="dynamic"))

    def __init__(self, patient_id, doctor_id, appointment_date, appointment_time,
                 reason_for_visit, status=AppointmentStatus.PENDING, review_notes=None):
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.appointment_date = appointment_date
        self.appointment_time = appointment_time
        self.reason_for_visit = reason_for_visit.strip() if reason_for_visit else ""
        self.status = status
        self.review_notes = review_notes.strip() if review_notes else None

    @property
    def patient_name(self):
        """Convenience property retrieving patient full name."""
        return self.patient.full_name if self.patient else "Unknown Patient"

    @property
    def doctor_name(self):
        """Convenience property retrieving doctor full name."""
        return self.doctor.full_name if self.doctor else "Unknown Doctor"

    @property
    def doctor_specialization(self):
        """Convenience property retrieving doctor specialization."""
        return self.doctor.specialization if self.doctor else "General"

    @property
    def formatted_date(self):
        """Formatted appointment date (e.g., Oct 24, 2026)."""
        return self.appointment_date.strftime("%b %d, %Y") if self.appointment_date else ""

    @property
    def formatted_time(self):
        """Formatted appointment time (e.g., 10:30 AM)."""
        return self.appointment_time.strftime("%I:%M %p") if self.appointment_time else ""

    @property
    def status_badge_class(self):
        """Returns Bootstrap badge color class corresponding to current status."""
        badge_map = {
            AppointmentStatus.PENDING: "warning text-dark",
            AppointmentStatus.APPROVED: "success",
            AppointmentStatus.REJECTED: "danger",
            AppointmentStatus.CANCELLED: "secondary",
            AppointmentStatus.COMPLETED: "info text-dark"
        }
        return badge_map.get(self.status, "secondary")

    def to_dict(self):
        """Serializes appointment entity into dictionary representation."""
        return {
            "appointment_id": self.appointment_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "doctor_specialization": self.doctor_specialization,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "appointment_time": self.appointment_time.strftime("%H:%M") if self.appointment_time else None,
            "reason_for_visit": self.reason_for_visit,
            "status": self.status,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Appointment id={self.appointment_id} pat={self.patient_id} doc={self.doctor_id} status='{self.status}'>"
