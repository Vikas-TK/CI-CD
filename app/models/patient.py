from datetime import datetime, timezone
from app import db


class Patient(db.Model):
    """
    Patient domain model representing clinical demographic and health profile.
    Linked 1-to-1 with the authenticated User entity.
    """
    __tablename__ = "patients"

    patient_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    aadhaar_number = db.Column(db.String(20), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    disease_or_complaint = db.Column(db.Text, nullable=True)
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 1-to-1 relationship with User model
    user = db.relationship("User", backref=db.backref("patient_profile", uselist=False, cascade="all, delete-orphan"))

    def __init__(self, user_id, age=None, gender=None, aadhaar_number=None, blood_group=None,
                 disease_or_complaint=None, emergency_contact_name=None, emergency_contact_phone=None,
                 address=None):
        self.user_id = user_id
        self.age = age
        self.gender = gender.strip() if gender else None
        self.aadhaar_number = aadhaar_number.strip().replace(" ", "").replace("-", "") if aadhaar_number else None
        self.blood_group = blood_group.strip() if blood_group else None
        self.disease_or_complaint = disease_or_complaint.strip() if disease_or_complaint else None
        self.emergency_contact_name = emergency_contact_name.strip() if emergency_contact_name else None
        self.emergency_contact_phone = emergency_contact_phone.strip() if emergency_contact_phone else None
        self.address = address.strip() if address else None

    @property
    def masked_aadhaar(self):
        """Returns masked Aadhaar number (e.g. XXXX-XXXX-1234) for privacy."""
        if not self.aadhaar_number:
            return "Not Provided"
        raw = self.aadhaar_number.replace(" ", "").replace("-", "")
        if len(raw) >= 4:
            return f"XXXX-XXXX-{raw[-4:]}"
        return "XXXX-XXXX-XXXX"

    @property
    def full_name(self):
        """Convenience property pulling name from associated user account."""
        return self.user.full_name if self.user else "Unknown Patient"

    @property
    def email(self):
        return self.user.email if self.user else ""

    @property
    def phone_number(self):
        return self.user.phone_number if self.user else ""

    def to_dict(self, include_sensitive=False):
        """Serialize patient details, masking Aadhaar unless authorized."""
        return {
            "patient_id": self.patient_id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "age": self.age,
            "gender": self.gender,
            "blood_group": self.blood_group,
            "disease_or_complaint": self.disease_or_complaint,
            "aadhaar_number": self.aadhaar_number if include_sensitive else self.masked_aadhaar,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone,
            "address": self.address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Patient patient_id={self.patient_id} user_id={self.user_id} name='{self.full_name}'>"
