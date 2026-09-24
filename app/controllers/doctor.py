from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.models.appointment import AppointmentStatus
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.appointment_service import AppointmentService
from app.utils.decorators import doctor_required

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/dashboard")
@doctor_required
def dashboard():
    """Doctor Dashboard overview displaying profile status, appointment metrics, and agenda."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    stats = AppointmentService.get_doctor_appointment_stats(doctor.doctor_id) if doctor else {}
    today_appointments = []
    if doctor:
        today_appointments = AppointmentService.get_doctor_appointments(doctor.doctor_id, status=AppointmentStatus.APPROVED)
    return render_template(
        "doctor/dashboard.html",
        user=current_user,
        doctor=doctor,
        stats=stats,
        today_appointments=today_appointments
    )


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


# ---------------------------------------------------------
# APPOINTMENT MANAGEMENT (MODULE 4)
# ---------------------------------------------------------

@doctor_bp.route("/appointments", methods=["GET"])
@doctor_required
def appointments_list():
    """Doctor views list of assigned patient appointments with status & date filters."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    status_filter = request.args.get("status")
    date_filter = request.args.get("date")

    appointments = AppointmentService.get_doctor_appointments(
        doctor_id=doctor.doctor_id,
        status=status_filter,
        date_filter=date_filter
    )
    stats = AppointmentService.get_doctor_appointment_stats(doctor.doctor_id)

    return render_template(
        "doctor/appointments/index.html",
        doctor=doctor,
        appointments=appointments,
        stats=stats,
        current_status=status_filter,
        current_date=date_filter,
        all_statuses=AppointmentStatus.ALL_STATUSES
    )


@doctor_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@doctor_required
def view_appointment(appointment_id):
    """Doctor views specific consultation request details."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    appointment = AppointmentService.get_appointment_by_id(appointment_id)
    if not appointment or appointment.doctor_id != doctor.doctor_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for("doctor.appointments_list"))

    return render_template("doctor/appointments/view.html", appointment=appointment, doctor=doctor)


@doctor_bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@doctor_required
def update_status(appointment_id):
    """Doctor reviews and updates status (Approved, Rejected, Completed) of an appointment."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    appointment = AppointmentService.get_appointment_by_id(appointment_id)
    if not appointment or appointment.doctor_id != doctor.doctor_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for("doctor.appointments_list"))

    new_status = request.form.get("status", "").strip()
    review_notes = request.form.get("review_notes", "").strip()

    updated, errors = AppointmentService.update_appointment_status(
        appointment_id=appointment_id,
        new_status=new_status,
        user=current_user,
        review_notes=review_notes
    )

    if errors:
        for err in errors:
            flash(err, "danger")
    else:
        flash(f"Appointment #{appointment_id} updated to '{new_status}'.", "success")

    return redirect(url_for("doctor.view_appointment", appointment_id=appointment_id))
