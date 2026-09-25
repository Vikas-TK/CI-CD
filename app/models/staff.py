from datetime import datetime, timezone
from app import db


class Staff(db.Model):
    """
    Staff domain model representing hospital administrative and clinical support staff.
    Linked 1-to-1 with the authenticated User entity.
    """
    __tablename__ = "staff"

    staff_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    designation = db.Column(db.String(100), nullable=False)
    aadhaar_number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 1-to-1 relationship with User model
    user = db.relationship("User", backref=db.backref("staff_profile", uselist=False, cascade="all, delete-orphan"))

    def __init__(self, user_id, designation, aadhaar_number=None):
        self.user_id = user_id
        self.designation = designation.strip() if designation else ""
        if aadhaar_number:
            self.aadhaar_number = aadhaar_number.strip().replace(" ", "").replace("-", "")
        else:
            self.aadhaar_number = None

    @property
    def full_name(self):
        """Convenience property pulling full name from associated user account."""
        return self.user.full_name if self.user else "Unknown Staff"

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

    @property
    def masked_aadhaar(self):
        """Returns masked Aadhaar number (e.g. XXXX-XXXX-1234) for privacy protection."""
        if not self.aadhaar_number:
            return "Not Provided"
        raw = self.aadhaar_number.replace(" ", "").replace("-", "")
        if len(raw) >= 4:
            return f"XXXX-XXXX-{raw[-4:]}"
        return "XXXX-XXXX-XXXX"

    def to_dict(self, include_sensitive=False):
        """Serializes staff profile for directory presentation and API responses."""
        return {
            "staff_id": self.staff_id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "designation": self.designation,
            "aadhaar_number": self.aadhaar_number if include_sensitive else self.masked_aadhaar,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Staff id={self.staff_id} user_id={self.user_id} designation='{self.designation}'>"
