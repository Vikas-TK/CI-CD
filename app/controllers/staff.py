from flask import Blueprint, render_template
from flask_login import current_user
from app.utils.decorators import staff_required

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/dashboard")
@staff_required
def dashboard():
    """Staff Dashboard overview."""
    return render_template("staff/dashboard.html", user=current_user)
