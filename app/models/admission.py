from datetime import datetime, timezone
from app import db


class AdmissionStatus:
    """Standardized Admission status values."""
    ACTIVE = "Active"
    DISCHARGED = "Discharged"
    CANCELLED = "Cancelled"

    ALL_STATUSES = [ACTIVE, DISCHARGED, CANCELLED]

    @classmethod
    def is_valid(cls, status):
        return status in cls.ALL_STATUSES


class Admission(db.Model):
    """
    Patient Admission / Inpatient Stay model linking Patient, Room, and Ward.
    Tracks check-in, check-out, operational stay status, reason for admission, and clinical discharge notes.
    """
    __tablename__ = "admissions"

    admission_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.room_id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    ward_id = db.Column(
        db.Integer,
        db.ForeignKey("wards.ward_id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    check_in_date = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    check_out_date = db.Column(
        db.DateTime,
        nullable=True,
        index=True
    )
    status = db.Column(
        db.String(20),
        nullable=False,
        default=AdmissionStatus.ACTIVE,
        index=True
    )
    reason = db.Column(db.Text, nullable=True)
    discharge_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    patient = db.relationship("Patient", backref=db.backref("admissions", lazy="dynamic", cascade="all, delete-orphan"))
    room = db.relationship("Room", backref=db.backref("admissions", lazy="dynamic"))
    ward = db.relationship("Ward", backref=db.backref("admissions", lazy="dynamic"))

    def __init__(self, patient_id, room_id, ward_id, check_in_date=None, check_out_date=None,
                 status=AdmissionStatus.ACTIVE, reason=None, discharge_notes=None):
        self.patient_id = int(patient_id)
        self.room_id = int(room_id)
        self.ward_id = int(ward_id)
        self.check_in_date = check_in_date if check_in_date else datetime.now(timezone.utc)
        self.check_out_date = check_out_date
        self.status = status if AdmissionStatus.is_valid(status) else AdmissionStatus.ACTIVE
        self.reason = reason.strip() if reason else None
        self.discharge_notes = discharge_notes.strip() if discharge_notes else None

    @property
    def is_active(self):
        """Returns True if admission is currently active."""
        return self.status == AdmissionStatus.ACTIVE

    @property
    def is_discharged(self):
        """Returns True if patient has been discharged."""
        return self.status == AdmissionStatus.DISCHARGED

    @property
    def is_cancelled(self):
        """Returns True if admission was cancelled."""
        return self.status == AdmissionStatus.CANCELLED

    @property
    def patient_name(self):
        return self.patient.full_name if self.patient else "Unknown Patient"

    @property
    def room_number(self):
        return self.room.room_number if self.room else "N/A"

    @property
    def ward_name(self):
        return self.ward.ward_name if self.ward else "N/A"

    @property
    def stay_duration_days(self):
        """Calculate number of days stayed so far or until discharge."""
        end_time = self.check_out_date or datetime.now(timezone.utc)
        # Handle naive vs aware datetimes gracefully
        start = self.check_in_date
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        diff = end_time - start
        return max(0, diff.days)

    def to_dict(self):
        return {
            "admission_id": self.admission_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "room_id": self.room_id,
            "room_number": self.room_number,
            "ward_id": self.ward_id,
            "ward_name": self.ward_name,
            "check_in_date": self.check_in_date.isoformat() if self.check_in_date else None,
            "check_out_date": self.check_out_date.isoformat() if self.check_out_date else None,
            "status": self.status,
            "reason": self.reason,
            "discharge_notes": self.discharge_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Admission {self.admission_id}: Patient={self.patient_id} Room={self.room_id} Ward={self.ward_id} Status={self.status}>"
