from flask import Blueprint, render_template
from flask_login import current_user
from app.utils.decorators import patient_required

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/dashboard")
@patient_required
def dashboard():
    """Patient Dashboard overview."""
    return render_template("patient/dashboard.html", user=current_user)
