from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.services.patient_service import PatientService
from app.utils.decorators import patient_required

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/dashboard")
@patient_required
def dashboard():
    """Patient Dashboard overview displaying profile completion status."""
    patient = PatientService.get_patient_by_user_id(current_user.user_id)
    return render_template("patient/dashboard.html", user=current_user, patient=patient)


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
