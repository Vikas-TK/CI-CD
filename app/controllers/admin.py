from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import current_user
from app.models.user import User, Role
from app.services.user_service import UserService
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

    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        total_doctors=total_doctors,
        total_staff=total_staff,
        total_patients=total_patients,
        total_pharmacy=total_pharmacy,
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
