from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.models.appointment import AppointmentStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.ward import Ward, WardStatus
from app.models.room import Room
from app.models.patient import Patient
from app.models.prescription import Prescription, PrescriptionItem, PrescriptionStatus
from app.models.medicine import Medicine
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.appointment_service import AppointmentService
from app.services.admission_service import AdmissionService
from app.services.prescription_service import PrescriptionService
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


# ---------------------------------------------------------
# ADMISSION MANAGEMENT - CLINICAL READ-ONLY VIEW (MODULE 8)
# ---------------------------------------------------------

@doctor_bp.route("/admissions", methods=["GET"])
@doctor_required
def admissions_list():
    """Doctor view of hospital inpatient admissions for clinical workflow coordination."""
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    ward_filter = request.args.get("ward_id", type=int)
    page = request.args.get("page", 1, type=int)

    pagination = AdmissionService.get_all_admissions(
        status=status_filter or None,
        ward_id=ward_filter,
        search=search_query or None,
        page=page,
        per_page=12
    )
    admissions = pagination.items
    wards = Ward.query.filter_by(status=WardStatus.ACTIVE).order_by(Ward.ward_name.asc()).all()

    return render_template(
        "doctor/admissions/index.html",
        admissions=admissions,
        pagination=pagination,
        wards=wards,
        search_query=search_query,
        current_status=status_filter,
        current_ward_id=ward_filter,
        all_statuses=AdmissionStatus.ALL_STATUSES
    )


@doctor_bp.route("/admissions/<int:admission_id>", methods=["GET"])
@doctor_required
def admission_details(admission_id):
    """Doctor clinical view of specific inpatient admission details."""
    admission = AdmissionService.get_admission_by_id(admission_id)
    if not admission:
        flash("Admission record not found.", "danger")
        return redirect(url_for("doctor.admissions_list"))

    return render_template("doctor/admissions/view.html", admission=admission)


# ---------------------------------------------------------
# PRESCRIPTION MANAGEMENT (MODULE 9)
# ---------------------------------------------------------

@doctor_bp.route("/prescriptions", methods=["GET"])
@doctor_required
def prescriptions_list():
    """Doctor view of prescriptions authored by the authenticated doctor."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = PrescriptionService.get_prescriptions_by_doctor(
        doctor_id=doctor.doctor_id,
        status=status_filter or None,
        search=search_query or None,
        page=page,
        per_page=10
    )
    prescriptions = pagination.items if pagination else []
    stats = PrescriptionService.get_prescription_stats(doctor_id=doctor.doctor_id)

    return render_template(
        "doctor/prescriptions/index.html",
        doctor=doctor,
        prescriptions=prescriptions,
        pagination=pagination,
        stats=stats,
        search_query=search_query,
        current_status=status_filter,
        all_statuses=PrescriptionStatus.ALL_STATUSES
    )


@doctor_bp.route("/prescriptions/create", methods=["GET", "POST"])
@doctor_required
def prescription_create():
    """Doctor form and handler to compose a multi-drug medical prescription."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        prescription_date = request.form.get("prescription_date", "").strip()
        notes = request.form.get("notes", "").strip()

        # Extract dynamic medicine items from form arrays
        medicine_ids = request.form.getlist("medicine_id[]") or request.form.getlist("medicine_id")
        dosages = request.form.getlist("dosage[]") or request.form.getlist("dosage")
        frequencies = request.form.getlist("frequency[]") or request.form.getlist("frequency")
        durations = request.form.getlist("duration[]") or request.form.getlist("duration")
        instructions_list = request.form.getlist("instructions[]") or request.form.getlist("instructions")

        items_data = []
        for i in range(len(medicine_ids)):
            if medicine_ids[i].strip():
                items_data.append({
                    "medicine_id": medicine_ids[i].strip(),
                    "dosage": dosages[i].strip() if i < len(dosages) else "",
                    "frequency": frequencies[i].strip() if i < len(frequencies) else "",
                    "duration": durations[i].strip() if i < len(durations) else "",
                    "instructions": instructions_list[i].strip() if i < len(instructions_list) else ""
                })

        # Handle JSON submission if submitted via AJAX/API
        if not items_data and request.is_json:
            json_body = request.get_json() or {}
            patient_id = json_body.get("patient_id", patient_id)
            prescription_date = json_body.get("prescription_date", prescription_date)
            notes = json_body.get("notes", notes)
            items_data = json_body.get("items", [])

        prescription, errors = PrescriptionService.create_prescription(
            doctor_id=doctor.doctor_id,
            patient_id=patient_id,
            items_data=items_data,
            prescription_date=prescription_date or None,
            notes=notes or None
        )

        if errors:
            for err in errors:
                flash(err, "danger")
            patients = Patient.query.all()
            medicines = PrescriptionService.get_all_medicines()
            return render_template(
                "doctor/prescriptions/create.html",
                doctor=doctor,
                patients=patients,
                medicines=medicines,
                form_data=request.form,
                prefilled_patient_id=patient_id
            ), 400

        flash(f"Prescription #RX{prescription.prescription_id:04d} issued successfully for '{prescription.patient_name}'.", "success")
        return redirect(url_for("doctor.prescription_details", prescription_id=prescription.prescription_id))

    preselected_patient_id = request.args.get("patient_id", type=int)
    patients = Patient.query.all()
    medicines = PrescriptionService.get_all_medicines()

    return render_template(
        "doctor/prescriptions/create.html",
        doctor=doctor,
        patients=patients,
        medicines=medicines,
        prefilled_patient_id=preselected_patient_id
    )


@doctor_bp.route("/prescriptions/<int:prescription_id>", methods=["GET"])
@doctor_required
def prescription_details(prescription_id):
    """Doctor detailed view of a prescription."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    prescription = PrescriptionService.get_prescription_by_id(prescription_id)
    if not prescription:
        flash("Prescription record not found.", "danger")
        return redirect(url_for("doctor.prescriptions_list"))

    return render_template(
        "doctor/prescriptions/view.html",
        doctor=doctor,
        prescription=prescription
    )


@doctor_bp.route("/prescriptions/<int:prescription_id>/status", methods=["POST"])
@doctor_required
def prescription_update_status(prescription_id):
    """Doctor updates the status of their prescription (e.g., Completed or Cancelled)."""
    doctor = DoctorService.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor.dashboard"))

    prescription = PrescriptionService.get_prescription_by_id(prescription_id)
    if not prescription or prescription.doctor_id != doctor.doctor_id:
        flash("Prescription not found or unauthorized.", "danger")
        return redirect(url_for("doctor.prescriptions_list"))

    new_status = request.form.get("status", "").strip()
    updated, errors = PrescriptionService.update_prescription_status(
        prescription_id=prescription_id,
        new_status=new_status,
        user=current_user
    )

    if errors:
        for err in errors:
            flash(err, "danger")
    else:
        flash(f"Prescription #RX{prescription_id:04d} status updated to '{new_status}'.", "success")

    return redirect(url_for("doctor.prescription_details", prescription_id=prescription_id))

