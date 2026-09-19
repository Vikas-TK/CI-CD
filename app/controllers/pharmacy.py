from flask import Blueprint, render_template
from flask_login import current_user
from app.utils.decorators import pharmacy_required

pharmacy_bp = Blueprint("pharmacy", __name__)


@pharmacy_bp.route("/dashboard")
@pharmacy_required
def dashboard():
    """Pharmacy Manager Dashboard overview."""
    return render_template("pharmacy/dashboard.html", user=current_user)
