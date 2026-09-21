from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import current_user
from app.models.user import User, Role
from app.models.patient import Patient
from app.services.user_service import UserService
from app.services.patient_service import PatientService
from app.utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """Administrator Dashboard with operational overview metrics."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_doctors = User.query.filter_by(role=Role.DOCTOR, is_active=True).count()
    total_staff = User.query.filter_by(role=Role.STAFF, is_active=True).count()
    total_patients = User.query.filter_by(role=Role.PATIENT, is_active=True).count()
    total_pharmacy = User.query.filter_by(role=Role.PHARMACY_MANAGER, is_active=True).count()
    total_patient_profiles = Patient.query.count()

    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        total_doctors=total_doctors,
        total_staff=total_staff,
        total_patients=total_patients,
        total_pharmacy=total_pharmacy,
        total_patient_profiles=total_patient_profiles,
        recent_users=recent_users
    )


@admin_bp.route("/users", methods=["GET"])
@admin_required
def users_list():
    """Administrator User Management table with search and filtering."""
    search_query = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    query = UserService.get_users(
        search_query=search_query,
        role_filter=role_filter,
        status_filter=status_filter
    )

    pagination = query.paginate(page=page, per_page=10, error_out=False)
    users = pagination.items

    return render_template(
        "admin/users.html",
        users=users,
        pagination=pagination,
        search_query=search_query,
        role_filter=role_filter,
        status_filter=status_filter,
        available_roles=Role.ALL_ROLES,
        privileged_roles=Role.PRIVILEGED_ROLES
    )


@admin_bp.route("/users/create", methods=["POST"])
@admin_required
def create_user():
    """Administrator endpoint to create privileged staff, doctor, pharmacy manager, or admin accounts."""
    first_name = request.form.get("first_name", "")
    last_name = request.form.get("last_name", "")
    email = request.form.get("email", "")
    phone_number = request.form.get("phone_number", "")
    password = request.form.get("password", "")
    role = request.form.get("role", Role.STAFF)
    is_active = request.form.get("is_active") == "1" or request.form.get("is_active") == "true" or "is_active" in request.form

    user, errors = UserService.create_privileged_user(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        password=password,
        role=role,
        is_active=is_active
    )

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("admin.users_list"))

    flash(f"User account for {user.full_name} ({user.role}) created successfully!", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_status(user_id):
    """Toggles active/inactive status for a user with self-deactivation protection."""
    success, message = UserService.toggle_user_status(
        target_user_id=user_id,
        current_admin_user_id=current_user.user_id
    )

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success, "message": message}), (200 if success else 400)

    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/change-role", methods=["POST"])
@admin_required
def change_role(user_id):
    """Changes a user's role with self-demotion protection."""
    new_role = request.form.get("role", "")
    success, message = UserService.update_user_role(
        target_user_id=user_id,
        new_role=new_role,
        current_admin_user_id=current_user.user_id
    )

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success, "message": message}), (200 if success else 400)

    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.users_list"))


# ==============================================================================
# MODULE 2: ADMINISTRATOR PATIENT MANAGEMENT
# ==============================================================================

@admin_bp.route("/patients", methods=["GET"])
@admin_required
def patients_list():
    """Administrator Patient Directory with search and pagination."""
    search_query = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)

    query = PatientService.list_patients(search_query=search_query)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    patients = pagination.items

    return render_template(
        "admin/patients/index.html",
        patients=patients,
        pagination=pagination,
        search_query=search_query
    )


@admin_bp.route("/patients/<int:patient_id>", methods=["GET"])
@admin_required
def patient_details(patient_id):
    """Administrator detailed patient profile view."""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        flash("Patient record not found.", "danger")
        return redirect(url_for("admin.patients_list"))

    return render_template("admin/patients/view.html", patient=patient)


@admin_bp.route("/patients/<int:patient_id>/edit", methods=["GET"])
@admin_required
def patient_edit(patient_id):
    """Administrator edit patient profile form."""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        flash("Patient record not found.", "danger")
        return redirect(url_for("admin.patients_list"))

    return render_template(
        "admin/patients/edit.html",
        patient=patient,
        blood_groups=PatientService.VALID_BLOOD_GROUPS,
        genders=PatientService.VALID_GENDERS
    )


@admin_bp.route("/patients/<int:patient_id>/update", methods=["POST"])
@admin_required
def patient_update(patient_id):
    """Administrator update patient profile handler."""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        flash("Patient record not found.", "danger")
        return redirect(url_for("admin.patients_list"))

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
            "admin/patients/edit.html",
            patient=patient,
            form_data=request.form,
            blood_groups=PatientService.VALID_BLOOD_GROUPS,
            genders=PatientService.VALID_GENDERS
        ), 400

    flash(f"Patient profile for {updated_patient.full_name} updated successfully.", "success")
    return redirect(url_for("admin.patient_details", patient_id=patient.patient_id))
