from datetime import datetime, timezone
from app import db


class DosageForm:
    """Standard controlled dosage forms for medicines."""
    TABLET = "Tablet"
    CAPSULE = "Capsule"
    SYRUP = "Syrup"
    INJECTION = "Injection"
    OINTMENT = "Ointment"
    DROPS = "Drops"
    INHALER = "Inhaler"
    OTHER = "Other"

    ALL_FORMS = [TABLET, CAPSULE, SYRUP, INJECTION, OINTMENT, DROPS, INHALER, OTHER]


class Medicine(db.Model):
    """
    Medicine domain model representing pharmaceutical drugs and medications.
    Serves as reference catalog for prescriptions (Module 9) and prepares
    clean normalization for Pharmacy Inventory (Module 10).
    """
    __tablename__ = "medicines"

    medicine_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    generic_name = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=True, index=True)
    dosage_form = db.Column(db.String(50), nullable=False, default=DosageForm.TABLET)
    strength = db.Column(db.String(50), nullable=True)  # e.g., '500 mg', '10 mg/ml'
    manufacturer = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, name, generic_name=None, category=None, dosage_form=DosageForm.TABLET,
                 strength=None, manufacturer=None):
        self.name = name.strip() if name else ""
        self.generic_name = generic_name.strip() if generic_name else None
        self.category = category.strip() if category else None
        self.dosage_form = dosage_form.strip() if dosage_form else DosageForm.TABLET
        self.strength = strength.strip() if strength else None
        self.manufacturer = manufacturer.strip() if manufacturer else None

    @property
    def display_name(self):
        """Returns descriptive name with strength if available."""
        if self.strength:
            return f"{self.name} ({self.strength}) - {self.dosage_form}"
        return f"{self.name} - {self.dosage_form}"

    def to_dict(self):
        """Serialize medicine details."""
        return {
            "medicine_id": self.medicine_id,
            "name": self.name,
            "generic_name": self.generic_name,
            "category": self.category,
            "dosage_form": self.dosage_form,
            "strength": self.strength,
            "manufacturer": self.manufacturer,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Medicine id={self.medicine_id} name='{self.name}' form='{self.dosage_form}'>"
