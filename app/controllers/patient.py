from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.models.appointment import AppointmentStatus
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.appointment_service import AppointmentService
from app.utils.decorators import patient_required

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/dashboard")
@patient_required
def dashboard():
    """Patient Dashboard overview displaying profile and appointment summary."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    stats = AppointmentService.get_patient_appointment_stats(patient.patient_id) if patient else {}
    recent_appointments = AppointmentService.get_patient_appointments(patient.patient_id)[:5] if patient else []
    return render_template(
        "patient/dashboard.html",
        user=current_user,
        patient=patient,
        stats=stats,
        recent_appointments=recent_appointments
    )


@patient_bp.route("/profile")
@patient_required
def view_profile():
    """View current authenticated patient's profile."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("You have not completed your patient profile yet. Please fill in your medical details.", "info")
        return redirect(url_for("patient.complete_profile"))

    return render_template("patient/profile.html", user=current_user, patient=patient)


@patient_bp.route("/profile/complete", methods=["GET", "POST"])
@patient_required
def complete_profile():
    """Form and submission handler to create initial patient profile."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if patient:
        flash("You already have an active patient profile.", "info")
        return redirect(url_for("patient.view_profile"))

    if request.method == "POST":
        age = request.form.get("age", "")
        gender = request.form.get("gender", "")
        aadhaar_number = request.form.get("aadhaar_number", "")
        blood_group = request.form.get("blood_group", "")
        disease_or_complaint = request.form.get("disease_or_complaint", "")
        emergency_contact_name = request.form.get("emergency_contact_name", "")
        emergency_contact_phone = request.form.get("emergency_contact_phone", "")
        address = request.form.get("address", "")

        new_patient, errors = PatientService.create_patient_profile(
            user_id=current_user.user_id,
            age=age,
            gender=gender,
            aadhaar_number=aadhaar_number,
            blood_group=blood_group,
            disease_or_complaint=disease_or_complaint,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            address=address
        )

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "patient/profile_form.html",
                is_new=True,
                form_data=request.form,
                blood_groups=PatientService.VALID_BLOOD_GROUPS,
                genders=PatientService.VALID_GENDERS
            ), 400

        flash("Your patient profile has been created successfully!", "success")
        return redirect(url_for("patient.view_profile"))

    return render_template(
        "patient/profile_form.html",
        is_new=True,
        form_data={},
        blood_groups=PatientService.VALID_BLOOD_GROUPS,
        genders=PatientService.VALID_GENDERS
    )


@patient_bp.route("/profile/edit", methods=["GET"])
@patient_required
def edit_profile():
    """Form to edit current patient's profile."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("Please complete your patient profile first.", "info")
        return redirect(url_for("patient.complete_profile"))

    return render_template(
        "patient/profile_form.html",
        is_new=False,
        patient=patient,
        blood_groups=PatientService.VALID_BLOOD_GROUPS,
        genders=PatientService.VALID_GENDERS
    )


@patient_bp.route("/profile/update", methods=["POST"])
@patient_required
def update_profile():
    """Submission handler to update current patient's profile."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("patient.complete_profile"))

    age = request.form.get("age", "")
    gender = request.form.get("gender", "")
    aadhaar_number = request.form.get("aadhaar_number", "")
    blood_group = request.form.get("blood_group", "")
    disease_or_complaint = request.form.get("disease_or_complaint", "")
    emergency_contact_name = request.form.get("emergency_contact_name", "")
    emergency_contact_phone = request.form.get("emergency_contact_phone", "")
    address = request.form.get("address", "")
    phone_number = request.form.get("phone_number", "")

    updated_patient, errors = PatientService.update_patient_profile(
        patient_id=patient.patient_id,
        updating_user=current_user,
        age=age,
        gender=gender,
        aadhaar_number=aadhaar_number,
        blood_group=blood_group,
        disease_or_complaint=disease_or_complaint,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone=emergency_contact_phone,
        address=address,
        phone_number=phone_number
    )

    if errors:
        for err in errors:
            flash(err, "danger")
        return render_template(
            "patient/profile_form.html",
            is_new=False,
            patient=patient,
            form_data=request.form,
            blood_groups=PatientService.VALID_BLOOD_GROUPS,
            genders=PatientService.VALID_GENDERS
        ), 400

    flash("Your profile was updated successfully.", "success")
    return redirect(url_for("patient.view_profile"))


# ---------------------------------------------------------
# APPOINTMENT MANAGEMENT (MODULE 4)
# ---------------------------------------------------------

@patient_bp.route("/appointments")
@patient_required
def list_appointments():
    """List all appointments for current authenticated patient."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("Please complete your patient profile before managing appointments.", "info")
        return redirect(url_for("patient.complete_profile"))

    status_filter = request.args.get("status")
    appointments = AppointmentService.get_patient_appointments(patient.patient_id, status=status_filter)
    stats = AppointmentService.get_patient_appointment_stats(patient.patient_id)

    return render_template(
        "patient/appointments/index.html",
        patient=patient,
        appointments=appointments,
        stats=stats,
        current_status=status_filter,
        all_statuses=AppointmentStatus.ALL_STATUSES
    )


@patient_bp.route("/appointments/request", methods=["GET", "POST"])
@patient_required
def request_appointment():
    """Form and submission handler to book a new appointment with a doctor."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("Please complete your patient profile before requesting an appointment.", "warning")
        return redirect(url_for("patient.complete_profile"))

    doctors = DoctorService.list_doctors(status_filter="active").all()

    if request.method == "POST":
        doctor_id = request.form.get("doctor_id", type=int)
        appt_date = request.form.get("appointment_date", "")
        appt_time = request.form.get("appointment_time", "")
        reason = request.form.get("reason_for_visit", "")

        appointment, errors = AppointmentService.create_appointment(
            patient_id=patient.patient_id,
            doctor_id=doctor_id,
            date_input=appt_date,
            time_input=appt_time,
            reason_for_visit=reason
        )

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "patient/appointments/request.html",
                patient=patient,
                doctors=doctors,
                form_data=request.form
            ), 400

        flash(
            f"Appointment request submitted successfully with Dr. {appointment.doctor_name}! Status: Pending approval.",
            "success"
        )
        return redirect(url_for("patient.list_appointments"))

    preselected_doctor_id = request.args.get("doctor_id", type=int)
    return render_template(
        "patient/appointments/request.html",
        patient=patient,
        doctors=doctors,
        form_data={"doctor_id": preselected_doctor_id} if preselected_doctor_id else {}
    )


@patient_bp.route("/appointments/<int:appointment_id>")
@patient_required
def view_appointment(appointment_id):
    """View appointment details for patient."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("Please complete your patient profile first.", "info")
        return redirect(url_for("patient.complete_profile"))

    appointment = AppointmentService.get_appointment_by_id(appointment_id)
    if not appointment or appointment.patient_id != patient.patient_id:
        flash("Appointment not found or unauthorized.", "danger")
        return redirect(url_for("patient.list_appointments"))

    return render_template("patient/appointments/view.html", appointment=appointment, patient=patient)


@patient_bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@patient_required
def cancel_appointment(appointment_id):
    """Cancel patient's appointment."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    if not patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("patient.list_appointments"))

    cancellation_reason = request.form.get("reason", "Cancelled by patient.")
    appointment, errors = AppointmentService.update_appointment_status(
        appointment_id=appointment_id,
        new_status=AppointmentStatus.CANCELLED,
        user=current_user,
        review_notes=cancellation_reason
    )

    if errors:
        for err in errors:
            flash(err, "danger")
    else:
        flash(f"Appointment #{appointment_id} has been cancelled.", "info")

    return redirect(url_for("patient.list_appointments"))
