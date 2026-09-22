from datetime import datetime, timezone
from app import db


class Doctor(db.Model):
    """
    Doctor domain model representing medical professional profile and specialization.
    Linked 1-to-1 with the authenticated User entity.
    """
    __tablename__ = "doctors"

    doctor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    specialization = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 1-to-1 relationship with User model
    user = db.relationship("User", backref=db.backref("doctor_profile", uselist=False, cascade="all, delete-orphan"))

    def __init__(self, user_id, specialization):
        self.user_id = user_id
        self.specialization = specialization.strip() if specialization else ""

    @property
    def full_name(self):
        """Convenience property pulling full name from associated user account."""
        return self.user.full_name if self.user else "Unknown Doctor"

    @property
    def email(self):
        """Convenience property pulling email from associated user account."""
        return self.user.email if self.user else ""

    @property
    def phone_number(self):
        """Convenience property pulling phone number from associated user account."""
        return self.user.phone_number if self.user else ""

    @property
    def is_active(self):
        """Convenience property pulling account active status from associated user account."""
        return self.user.is_active if self.user else False

    @property
    def role(self):
        """Convenience property pulling role from associated user account."""
        return self.user.role if self.user else ""

    def to_dict(self):
        """Serializes doctor profile for directory presentation and API responses."""
        return {
            "doctor_id": self.doctor_id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "specialization": self.specialization,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Doctor id={self.doctor_id} user_id={self.user_id} spec='{self.specialization}'>"
