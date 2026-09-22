from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.utils.decorators import doctor_required

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/dashboard")
@doctor_required
def dashboard():
    """Doctor Dashboard overview displaying profile status and clinical shortcuts."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    return render_template("doctor/dashboard.html", user=current_user, doctor=doctor)


@doctor_bp.route("/profile")
@doctor_required
def view_profile():
    """Doctor views their own professional profile."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    return render_template("doctor/profile.html", user=current_user, doctor=doctor)


@doctor_bp.route("/profile/edit", methods=["GET"])
@doctor_required
def edit_profile():
    """Doctor views form to update their own permitted profile fields."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found. Please contact an administrator.", "warning")
        return redirect(url_for("doctor.dashboard"))

    return render_template(
        "doctor/profile_edit.html",
        user=current_user,
        doctor=doctor,
        specializations=DoctorService.VALID_SPECIALIZATIONS
    )


@doctor_bp.route("/profile/update", methods=["POST"])
@doctor_required
def update_profile():
    """Doctor updates their own permitted profile fields."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found. Please contact an administrator.", "warning")
        return redirect(url_for("doctor.dashboard"))

    specialization = request.form.get("specialization", "")
    phone_number = request.form.get("phone_number", "")

    updated_doc, errors = DoctorService.update_doctor_profile(
        doctor_id=doctor.doctor_id,
        updating_user=current_user,
        specialization=specialization,
        phone_number=phone_number
    )

    if errors:
        for err in errors:
            flash(err, "danger")
        return render_template(
            "doctor/profile_edit.html",
            user=current_user,
            doctor=doctor,
            form_data=request.form,
            specializations=DoctorService.VALID_SPECIALIZATIONS
        ), 400

    flash("Your doctor profile has been updated successfully.", "success")
    return redirect(url_for("doctor.view_profile"))


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
