from flask import Blueprint, render_template
from flask_login import current_user
from app.utils.decorators import doctor_required

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/dashboard")
@doctor_required
def dashboard():
    """Doctor Dashboard overview."""
    return render_template("doctor/dashboard.html", user=current_user)
