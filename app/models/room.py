from datetime import datetime, timezone
from app import db


class RoomType:
    """Standardized Room Type categories for Hospital Management System."""
    SINGLE = "Single"
    DOUBLE = "Double"
    DELUXE = "Deluxe"
    ICU = "ICU"
    OTHER = "Other"

    ALL_TYPES = [SINGLE, DOUBLE, DELUXE, ICU, OTHER]

    @classmethod
    def is_valid(cls, room_type):
        return room_type in cls.ALL_TYPES


class RoomStatus:
    """Standardized Room operational status states."""
    AVAILABLE = "Available"
    OCCUPIED = "Occupied"
    MAINTENANCE = "Maintenance"

    ALL_STATUSES = [AVAILABLE, OCCUPIED, MAINTENANCE]

    @classmethod
    def is_valid(cls, status):
        return status in cls.ALL_STATUSES


class Room(db.Model):
    """
    Room domain model representing a physical room in hospital facilities.
    Tracks structural location (floor, block), type, and current operational status.
    Designed for seamless future integration with the Admission / Inpatient Stay module.
    """
    __tablename__ = "rooms"

    room_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    room_type = db.Column(db.String(30), nullable=False, default=RoomType.SINGLE, index=True)
    floor = db.Column(db.Integer, nullable=False, index=True)
    block = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=RoomStatus.AVAILABLE, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, room_number, room_type=RoomType.SINGLE, floor=1, block="Block A", status=RoomStatus.AVAILABLE):
        self.room_number = str(room_number).strip()
        self.room_type = room_type if RoomType.is_valid(room_type) else RoomType.SINGLE
        self.floor = int(floor)
        self.block = block.strip() if block else "Block A"
        self.status = status if RoomStatus.is_valid(status) else RoomStatus.AVAILABLE

    @property
    def is_available(self):
        """Returns True if room is ready to accept patient admission."""
        return self.status == RoomStatus.AVAILABLE

    @property
    def is_occupied(self):
        """Returns True if room is currently occupied by an admitted patient."""
        return self.status == RoomStatus.OCCUPIED

    @property
    def is_maintenance(self):
        """Returns True if room is undergoing sanitation or structural repair."""
        return self.status == RoomStatus.MAINTENANCE

    @property
    def status_badge_class(self):
        """Bootstrap badge styling helper according to operational status."""
        badge_map = {
            RoomStatus.AVAILABLE: "bg-success-subtle text-success border border-success-subtle",
            RoomStatus.OCCUPIED: "bg-danger-subtle text-danger border border-danger-subtle",
            RoomStatus.MAINTENANCE: "bg-warning-subtle text-warning border border-warning-subtle"
        }
        return badge_map.get(self.status, "bg-secondary-subtle text-secondary")

    @property
    def type_badge_class(self):
        """Bootstrap badge styling helper according to room category."""
        badge_map = {
            RoomType.ICU: "bg-danger text-white",
            RoomType.DELUXE: "bg-primary text-white",
            RoomType.SINGLE: "bg-info text-dark",
            RoomType.DOUBLE: "bg-secondary text-white",
            RoomType.OTHER: "bg-dark text-white"
        }
        return badge_map.get(self.room_type, "bg-secondary text-white")

    def to_dict(self):
        """Serializes room details for API responses and operational presentation."""
        return {
            "room_id": self.room_id,
            "room_number": self.room_number,
            "room_type": self.room_type,
            "floor": self.floor,
            "block": self.block,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Room #{self.room_number} Type={self.room_type} Floor={self.floor} Block={self.block} Status={self.status}>"
