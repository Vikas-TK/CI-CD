from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.models.appointment import AppointmentStatus
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.appointment_service import AppointmentService
from app.utils.decorators import staff_required

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/dashboard")
@staff_required
def dashboard():
    """Staff Dashboard overview with appointment overview stats."""
    appointment_stats = AppointmentService.get_hospital_appointment_stats()
    return render_template("staff/dashboard.html", user=current_user, stats=appointment_stats)


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


# ---------------------------------------------------------
# APPOINTMENT MANAGEMENT (MODULE 4)
# ---------------------------------------------------------

@staff_bp.route("/appointments", methods=["GET"])
@staff_required
def appointments_list():
    """Staff view of all hospital appointments with filtering and search."""
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    date_filter = request.args.get("date", "").strip()
    doctor_filter = request.args.get("doctor_id", type=int)
    patient_filter = request.args.get("patient_id", type=int)
    page = request.args.get("page", 1, type=int)

    pagination = AppointmentService.get_all_appointments(
        status=status_filter or None,
        date_filter=date_filter or None,
        doctor_id=doctor_filter,
        patient_id=patient_filter,
        search=search_query or None,
        page=page,
        per_page=12
    )
    appointments = pagination.items
    stats = AppointmentService.get_hospital_appointment_stats()
    doctors = DoctorService.list_doctors().all()

    return render_template(
        "admin/appointments/index.html",
        appointments=appointments,
        pagination=pagination,
        stats=stats,
        doctors=doctors,
        search_query=search_query,
        current_status=status_filter,
        current_date=date_filter,
        current_doctor_id=doctor_filter,
        all_statuses=AppointmentStatus.ALL_STATUSES,
        is_staff=True
    )


@staff_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@staff_required
def appointment_details(appointment_id):
    """Staff view of specific appointment details."""
    appointment = AppointmentService.get_appointment_by_id(appointment_id)
    if not appointment:
        flash("Appointment record not found.", "danger")
        return redirect(url_for("staff.appointments_list"))

    return render_template("admin/appointments/view.html", appointment=appointment, is_staff=True)


@staff_bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@staff_required
def appointment_update_status(appointment_id):
    """Staff update appointment status (Approved, Rejected, Cancelled, Completed)."""
    appointment = AppointmentService.get_appointment_by_id(appointment_id)
    if not appointment:
        flash("Appointment record not found.", "danger")
        return redirect(url_for("staff.appointments_list"))

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

    return redirect(url_for("staff.appointment_details", appointment_id=appointment_id))
