from app.controllers.main import main_bp
from app.controllers.auth import auth_bp
from app.controllers.admin import admin_bp
from app.controllers.doctor import doctor_bp
from app.controllers.staff import staff_bp
from app.controllers.patient import patient_bp
from app.controllers.pharmacy import pharmacy_bp

__all__ = [
    "main_bp",
    "auth_bp",
    "admin_bp",
    "doctor_bp",
    "staff_bp",
    "patient_bp",
    "pharmacy_bp"
]
