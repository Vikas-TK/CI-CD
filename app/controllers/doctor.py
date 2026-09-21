from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.services.patient_service import PatientService
from app.utils.decorators import doctor_required

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/dashboard")
@doctor_required
def dashboard():
    """Doctor Dashboard overview."""
    return render_template("doctor/dashboard.html", user=current_user)


@doctor_bp.route("/patients", methods=["GET"])
@doctor_required
def patients_list():
    """Doctor view of patient registry for clinical consultation lookup."""
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


@doctor_bp.route("/patients/<int:patient_id>", methods=["GET"])
@doctor_required
def patient_details(patient_id):
    """Doctor detailed view of patient profile."""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        flash("Patient record not found.", "danger")
        return redirect(url_for("doctor.patients_list"))

    return render_template("admin/patients/view.html", patient=patient, is_readonly=True)
