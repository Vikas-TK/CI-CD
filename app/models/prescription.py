from datetime import datetime, timezone
from app import db


class PrescriptionStatus:
    """Controlled prescription status state machine values."""
    ACTIVE = "Active"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

    ALL_STATUSES = [ACTIVE, COMPLETED, CANCELLED]


class Prescription(db.Model):
    """
    Prescription domain model representing an official medical order issued by a Doctor for a Patient.
    Maintains 1-to-many relationship with PrescriptionItem for normalized multi-drug prescribing.
    """
    __tablename__ = "prescriptions"

    prescription_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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
    prescription_date = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default=PrescriptionStatus.ACTIVE,
        index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    patient = db.relationship("Patient", backref=db.backref("prescriptions", lazy="dynamic", cascade="all, delete-orphan"))
    doctor = db.relationship("Doctor", backref=db.backref("prescriptions", lazy="dynamic", cascade="all, delete-orphan"))
    items = db.relationship(
        "PrescriptionItem",
        backref="prescription",
        lazy="joined",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.prescription_item_id.asc()"
    )

    def __init__(self, patient_id, doctor_id, prescription_date=None, notes=None,
                 status=PrescriptionStatus.ACTIVE):
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.prescription_date = prescription_date or datetime.now(timezone.utc)
        self.notes = notes.strip() if notes else None
        self.status = status.strip() if status else PrescriptionStatus.ACTIVE

    @property
    def patient_name(self):
        """Convenience property retrieving patient's full name."""
        return self.patient.full_name if self.patient else "Unknown Patient"

    @property
    def doctor_name(self):
        """Convenience property retrieving prescribing doctor's full name."""
        return self.doctor.full_name if self.doctor else "Unknown Doctor"

    @property
    def doctor_specialization(self):
        """Convenience property retrieving prescribing doctor's specialization."""
        return self.doctor.specialization if self.doctor else ""

    @property
    def is_active(self):
        return self.status == PrescriptionStatus.ACTIVE

    @property
    def is_completed(self):
        return self.status == PrescriptionStatus.COMPLETED

    @property
    def is_cancelled(self):
        return self.status == PrescriptionStatus.CANCELLED

    @property
    def item_count(self):
        return len(self.items) if self.items else 0

    @property
    def formatted_date(self):
        if self.prescription_date:
            return self.prescription_date.strftime("%b %d, %Y")
        return "N/A"

    def to_dict(self):
        """Serializes prescription along with child items."""
        return {
            "prescription_id": self.prescription_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "doctor_specialization": self.doctor_specialization,
            "prescription_date": self.prescription_date.isoformat() if self.prescription_date else None,
            "formatted_date": self.formatted_date,
            "notes": self.notes,
            "status": self.status,
            "item_count": self.item_count,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Prescription id={self.prescription_id} patient={self.patient_id} doctor={self.doctor_id} status='{self.status}'>"


class PrescriptionItem(db.Model):
    """
    PrescriptionItem domain model representing individual prescribed medicine line item.
    Enforces normalized 1-to-many relationship per prescription with dosage instructions.
    """
    __tablename__ = "prescription_items"
    __table_args__ = (
        db.UniqueConstraint("prescription_id", "medicine_id", name="uq_prescription_medicine"),
    )

    prescription_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prescription_id = db.Column(
        db.Integer,
        db.ForeignKey("prescriptions.prescription_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey("medicines.medicine_id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    dosage = db.Column(db.String(50), nullable=False)  # e.g., '500 mg', '1 tablet'
    frequency = db.Column(db.String(50), nullable=False)  # e.g., '2 times/day', 'Once daily'
    duration = db.Column(db.String(50), nullable=False)  # e.g., '5 days', '2 weeks'
    instructions = db.Column(db.String(255), nullable=True)  # e.g., 'After meals', 'With warm water'
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    medicine = db.relationship("Medicine", backref=db.backref("prescription_items", lazy="dynamic"))

    def __init__(self, prescription_id, medicine_id, dosage, frequency, duration, instructions=None):
        self.prescription_id = prescription_id
        self.medicine_id = medicine_id
        self.dosage = dosage.strip() if dosage else ""
        self.frequency = frequency.strip() if frequency else ""
        self.duration = duration.strip() if duration else ""
        self.instructions = instructions.strip() if instructions else None

    @property
    def medicine_name(self):
        """Convenience property retrieving prescribed drug name."""
        return self.medicine.name if self.medicine else "Unknown Medicine"

    @property
    def medicine_form(self):
        return self.medicine.dosage_form if self.medicine else ""

    @property
    def medicine_strength(self):
        return self.medicine.strength if self.medicine else ""

    def to_dict(self):
        return {
            "prescription_item_id": self.prescription_item_id,
            "prescription_id": self.prescription_id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine_name,
            "medicine_form": self.medicine_form,
            "medicine_strength": self.medicine_strength,
            "dosage": self.dosage,
            "frequency": self.frequency,
            "duration": self.duration,
            "instructions": self.instructions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<PrescriptionItem id={self.prescription_item_id} rx={self.prescription_id} med={self.medicine_id} dosage='{self.dosage}'>"
