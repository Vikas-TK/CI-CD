from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.models.patient import Patient
from app.models.appointment import AppointmentStatus
from app.models.room import Room, RoomType, RoomStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.admission import Admission, AdmissionStatus
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.staff_service import StaffService
from app.services.appointment_service import AppointmentService
from app.services.room_service import RoomService
from app.services.ward_service import WardService
from app.services.admission_service import AdmissionService
from app.utils.decorators import staff_required

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/dashboard")
@staff_required
def dashboard():
    """Staff Dashboard overview with appointment, room, and ward stats and profile badge."""
    staff_profile = StaffService.get_staff_by_user_id(current_user.user_id)
    appointment_stats = AppointmentService.get_hospital_appointment_stats()
    room_stats = RoomService.get_room_stats()
    ward_stats = WardService.get_ward_stats()
    admission_stats = AdmissionService.get_admission_stats()
    return render_template(
        "staff/dashboard.html",
        user=current_user,
        staff=staff_profile,
        stats=appointment_stats,
        room_stats=room_stats,
        ward_stats=ward_stats,
        admission_stats=admission_stats
    )



# ---------------------------------------------------------
# STAFF SELF-SERVICE (MODULE 5)
# ---------------------------------------------------------

@staff_bp.route("/profile", methods=["GET"])
@staff_required
def profile():
    """Staff self-service view of authenticated user's profile."""
    staff = StaffService.get_staff_by_user_id(current_user.user_id)
    return render_template("staff/profile.html", user=current_user, staff=staff)


@staff_bp.route("/profile/edit", methods=["GET"])
@staff_required
def profile_edit():
    """Staff self-service form to edit own contact and Aadhaar information."""
    staff = StaffService.get_staff_by_user_id(current_user.user_id)
    return render_template("staff/profile_edit.html", user=current_user, staff=staff)


@staff_bp.route("/profile/update", methods=["POST"])
@staff_required
def profile_update():
    """Staff self-service update handler."""
    staff = StaffService.get_staff_by_user_id(current_user.user_id)
    if not staff:
        flash("Staff profile record not found. Contact administrator.", "danger")
        return redirect(url_for("staff.dashboard"))

    phone_number = request.form.get("phone_number", "")
    aadhaar_number = request.form.get("aadhaar_number", "")

    updated_staff, errors = StaffService.update_staff_profile(
        staff_id=staff.staff_id,
        updating_user=current_user,
        phone_number=phone_number,
        aadhaar_number=aadhaar_number
    )

    if errors:
        for err in errors:
            flash(err, "danger")
        return render_template(
            "staff/profile_edit.html",
            user=current_user,
            staff=staff,
            form_data=request.form
        ), 400

    flash("Your profile information has been updated successfully.", "success")
    return redirect(url_for("staff.profile"))


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


# ---------------------------------------------------------
# ROOM INVENTORY DIRECTORY (MODULE 6)
# ---------------------------------------------------------

@staff_bp.route("/rooms", methods=["GET"])
@staff_required
def rooms_list():
    """Staff view of hospital room inventory with search, filtering, and availability stats."""
    search_query = request.args.get("search", "").strip()
    room_type = request.args.get("room_type", "").strip()
    status = request.args.get("status", "").strip()
    floor = request.args.get("floor", "").strip()
    block = request.args.get("block", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = RoomService.get_all_rooms(
        room_type=room_type or None,
        status=status or None,
        floor=floor or None,
        block=block or None,
        search=search_query or None,
        page=page,
        per_page=12
    )
    rooms = pagination.items
    stats = RoomService.get_room_stats()
    unique_floors = RoomService.get_unique_floors()
    unique_blocks = RoomService.get_unique_blocks()

    return render_template(
        "staff/rooms/index.html",
        rooms=rooms,
        pagination=pagination,
        stats=stats,
        search_query=search_query,
        current_type=room_type,
        current_status=status,
        current_floor=floor,
        current_block=block,
        all_types=RoomType.ALL_TYPES,
        all_statuses=RoomStatus.ALL_STATUSES,
        unique_floors=unique_floors,
        unique_blocks=unique_blocks,
        is_readonly=True
    )


@staff_bp.route("/rooms/<int:room_id>", methods=["GET"])
@staff_required
def room_details(room_id):
    """Staff detailed read-only view of a room."""
    room = RoomService.get_room_by_id(room_id)
    if not room:
        flash("Room record not found.", "danger")
        return redirect(url_for("staff.rooms_list"))

    return render_template("staff/rooms/view.html", room=room, is_readonly=True)


# ---------------------------------------------------------
# WARD INVENTORY DIRECTORY (MODULE 7)
# ---------------------------------------------------------

@staff_bp.route("/wards", methods=["GET"])
@staff_required
def wards_list():
    """Staff view of hospital ward inventory with search, filtering, and capacity stats."""
    search_query = request.args.get("search", "").strip()
    ward_type = request.args.get("ward_type", "").strip()
    status = request.args.get("status", "").strip()
    floor = request.args.get("floor", "").strip()
    block = request.args.get("block", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = WardService.get_all_wards(
        ward_type=ward_type or None,
        status=status or None,
        floor=floor or None,
        block=block or None,
        search=search_query or None,
        page=page,
        per_page=12
    )
    wards = pagination.items
    stats = WardService.get_ward_stats()
    unique_floors = WardService.get_unique_floors()
    unique_blocks = WardService.get_unique_blocks()

    return render_template(
        "staff/wards/index.html",
        wards=wards,
        pagination=pagination,
        stats=stats,
        search_query=search_query,
        current_type=ward_type,
        current_status=status,
        current_floor=floor,
        current_block=block,
        all_types=WardType.ALL_TYPES,
        all_statuses=WardStatus.ALL_STATUSES,
        unique_floors=unique_floors,
        unique_blocks=unique_blocks,
        is_readonly=True
    )


@staff_bp.route("/wards/<int:ward_id>", methods=["GET"])
@staff_required
def ward_details(ward_id):
    """Staff detailed read-only view of a ward."""
    ward = WardService.get_ward_by_id(ward_id)
    if not ward:
        flash("Ward record not found.", "danger")
        return redirect(url_for("staff.wards_list"))

    return render_template("staff/wards/view.html", ward=ward, is_readonly=True)


# ==============================================================================
# MODULE 8: STAFF PATIENT ADMISSION / STAY MANAGEMENT
# ==============================================================================

@staff_bp.route("/admissions", methods=["GET"])
@staff_required
def admissions_list():
    """Staff view of patient admission directory with status and ward filters."""
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    ward_filter = request.args.get("ward_id", type=int)
    room_filter = request.args.get("room_id", type=int)
    patient_filter = request.args.get("patient_id", type=int)
    page = request.args.get("page", 1, type=int)

    pagination = AdmissionService.get_all_admissions(
        status=status_filter or None,
        ward_id=ward_filter,
        room_id=room_filter,
        patient_id=patient_filter,
        search=search_query or None,
        page=page,
        per_page=12
    )
    admissions = pagination.items
    stats = AdmissionService.get_admission_stats()
    wards = Ward.query.filter_by(status=WardStatus.ACTIVE).order_by(Ward.ward_name.asc()).all()
    rooms = Room.query.order_by(Room.floor.asc(), Room.room_number.asc()).all()

    return render_template(
        "staff/admissions/index.html",
        admissions=admissions,
        pagination=pagination,
        stats=stats,
        wards=wards,
        rooms=rooms,
        search_query=search_query,
        current_status=status_filter,
        current_ward_id=ward_filter,
        current_room_id=room_filter,
        all_statuses=AdmissionStatus.ALL_STATUSES
    )


@staff_bp.route("/admissions/create", methods=["GET", "POST"])
@staff_required
def admission_create():
    """Staff interface to admit a patient to an available room and active ward."""
    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        room_id = request.form.get("room_id", "").strip()
        ward_id = request.form.get("ward_id", "").strip()
        check_in_date = request.form.get("check_in_date", "").strip()
        reason = request.form.get("reason", "").strip()

        admission, errors = AdmissionService.admit_patient(
            patient_id=patient_id,
            room_id=room_id,
            ward_id=ward_id,
            check_in_date=check_in_date or None,
            reason=reason or None
        )

        if errors:
            for err in errors:
                flash(err, "danger")
            patients = Patient.query.all()
            available_rooms = Room.query.filter_by(status=RoomStatus.AVAILABLE).order_by(Room.floor.asc(), Room.room_number.asc()).all()
            active_wards = Ward.query.filter_by(status=WardStatus.ACTIVE).order_by(Ward.ward_name.asc()).all()
            return render_template(
                "staff/admissions/create.html",
                patients=patients,
                available_rooms=available_rooms,
                active_wards=active_wards,
                form_data=request.form
            ), 400

        flash(
            f"Patient '{admission.patient_name}' successfully admitted (#ADM{admission.admission_id:04d}) to Room {admission.room_number} ({admission.ward_name}).",
            "success"
        )
        return redirect(url_for("staff.admission_details", admission_id=admission.admission_id))

    patients = Patient.query.all()
    available_rooms = Room.query.filter_by(status=RoomStatus.AVAILABLE).order_by(Room.floor.asc(), Room.room_number.asc()).all()
    active_wards = Ward.query.filter_by(status=WardStatus.ACTIVE).order_by(Ward.ward_name.asc()).all()

    return render_template(
        "staff/admissions/create.html",
        patients=patients,
        available_rooms=available_rooms,
        active_wards=active_wards
    )


@staff_bp.route("/admissions/<int:admission_id>", methods=["GET"])
@staff_required
def admission_details(admission_id):
    """Staff detailed view of an admission record."""
    admission = AdmissionService.get_admission_by_id(admission_id)
    if not admission:
        flash("Admission record not found.", "danger")
        return redirect(url_for("staff.admissions_list"))

    return render_template("staff/admissions/view.html", admission=admission)


@staff_bp.route("/admissions/<int:admission_id>/discharge", methods=["POST"])
@staff_required
def admission_discharge(admission_id):
    """Staff discharge patient action handler."""
    discharge_notes = request.form.get("discharge_notes", "").strip()
    check_out_date = request.form.get("check_out_date", "").strip()

    admission, errors = AdmissionService.discharge_patient(
        admission_id=admission_id,
        check_out_date=check_out_date or None,
        discharge_notes=discharge_notes or None
    )

    if errors:
        for err in errors:
            flash(err, "danger")
    else:
        flash(
            f"Patient '{admission.patient_name}' discharged successfully. Room {admission.room_number} is now Available.",
            "success"
        )

    return redirect(url_for("staff.admission_details", admission_id=admission_id))

