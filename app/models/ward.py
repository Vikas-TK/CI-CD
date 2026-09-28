from datetime import datetime, timezone
from app import db


class WardType:
    """Standardized Ward Type categories for Hospital Management System."""
    GENERAL = "General Ward"
    ICU = "ICU"
    EMERGENCY = "Emergency Ward"
    PEDIATRIC = "Pediatric Ward"
    MATERNITY = "Maternity Ward"
    SURGICAL = "Surgical Ward"
    OTHER = "Other"

    ALL_TYPES = [GENERAL, ICU, EMERGENCY, PEDIATRIC, MATERNITY, SURGICAL, OTHER]

    @classmethod
    def is_valid(cls, ward_type):
        return ward_type in cls.ALL_TYPES


class WardStatus:
    """Standardized Ward operational status states."""
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    MAINTENANCE = "Maintenance"

    ALL_STATUSES = [ACTIVE, INACTIVE, MAINTENANCE]

    @classmethod
    def is_valid(cls, status):
        return status in cls.ALL_STATUSES


class Ward(db.Model):
    """
    Ward domain model representing a clinical inpatient ward in hospital facilities.
    Tracks structural location (floor, block), category type, bed capacity, and operational status.
    Designed for seamless future integration with the Admission / Inpatient Stay module.
    """
    __tablename__ = "wards"

    ward_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ward_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    ward_type = db.Column(db.String(50), nullable=False, default=WardType.GENERAL, index=True)
    floor = db.Column(db.Integer, nullable=False, index=True)
    block = db.Column(db.String(50), nullable=False, index=True)
    capacity = db.Column(db.Integer, nullable=False, default=10)
    status = db.Column(db.String(20), nullable=False, default=WardStatus.ACTIVE, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, ward_name, ward_type=WardType.GENERAL, floor=1, block="Block A", capacity=10, status=WardStatus.ACTIVE):
        self.ward_name = str(ward_name).strip() if ward_name else ""
        self.ward_type = ward_type if WardType.is_valid(ward_type) else WardType.GENERAL
        self.floor = int(floor)
        self.block = block.strip() if block else "Block A"
        self.capacity = int(capacity) if capacity else 10
        self.status = status if WardStatus.is_valid(status) else WardStatus.ACTIVE

    @property
    def is_active(self):
        """Returns True if ward is active and operational."""
        return self.status == WardStatus.ACTIVE

    @property
    def is_inactive(self):
        """Returns True if ward is currently inactive."""
        return self.status == WardStatus.INACTIVE

    @property
    def is_maintenance(self):
        """Returns True if ward is under sanitation or maintenance."""
        return self.status == WardStatus.MAINTENANCE

    @property
    def status_badge_class(self):
        """Bootstrap badge styling helper according to operational status."""
        badge_map = {
            WardStatus.ACTIVE: "bg-success-subtle text-success border border-success-subtle",
            WardStatus.INACTIVE: "bg-secondary-subtle text-secondary border border-secondary-subtle",
            WardStatus.MAINTENANCE: "bg-warning-subtle text-warning border border-warning-subtle"
        }
        return badge_map.get(self.status, "bg-secondary-subtle text-secondary")

    @property
    def type_badge_class(self):
        """Bootstrap badge styling helper according to ward category."""
        badge_map = {
            WardType.ICU: "bg-danger text-white",
            WardType.EMERGENCY: "bg-warning text-dark",
            WardType.SURGICAL: "bg-primary text-white",
            WardType.PEDIATRIC: "bg-info text-dark",
            WardType.MATERNITY: "bg-success text-white",
            WardType.GENERAL: "bg-secondary text-white",
            WardType.OTHER: "bg-dark text-white"
        }
        return badge_map.get(self.ward_type, "bg-secondary text-white")

    def to_dict(self):
        """Serializes ward details for API responses and operational presentation."""
        return {
            "ward_id": self.ward_id,
            "ward_name": self.ward_name,
            "ward_type": self.ward_type,
            "floor": self.floor,
            "block": self.block,
            "capacity": self.capacity,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Ward id={self.ward_id} name='{self.ward_name}' type='{self.ward_type}' capacity={self.capacity} status='{self.status}'>"
