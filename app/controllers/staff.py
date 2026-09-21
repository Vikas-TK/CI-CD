from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.services.patient_service import PatientService
from app.utils.decorators import staff_required

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/dashboard")
@staff_required
def dashboard():
    """Staff Dashboard overview."""
    return render_template("staff/dashboard.html", user=current_user)


@staff_bp.route("/patients", methods=["GET"])
@staff_required
def patients_list():
    """Staff view of patient registry for admissions and front-desk reception."""
    search_query = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)

    query = PatientService.list_patients(search_query=search_query)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    patients = pagination.items

    return render_template(
        "admin/patients/index.html",
        patients=patients,
        pagination=pagination,
        search_query=search_query,
        is_readonly=True
    )


@staff_bp.route("/patients/<int:patient_id>", methods=["GET"])
@staff_required
def patient_details(patient_id):
    """Staff detailed view of patient profile."""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        flash("Patient record not found.", "danger")
        return redirect(url_for("staff.patients_list"))

    return render_template("admin/patients/view.html", patient=patient, is_readonly=True)
