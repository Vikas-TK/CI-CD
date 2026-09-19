from functools import wraps
from flask import abort, flash, redirect, url_for, request, jsonify, render_template
from flask_login import current_user
from app.models.user import Role


def role_required(*allowed_roles):
    """
    Decorator to enforce Role-Based Access Control on Flask routes.
    
    Usage:
        @role_required(Role.ADMINISTRATOR)
        @role_required(Role.DOCTOR, Role.STAFF)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required."}), 401
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login", next=request.url))

            if not current_user.is_active:
                flash("Your account has been deactivated. Please contact an administrator.", "danger")
                return redirect(url_for("auth.logout"))

            if current_user.role not in allowed_roles:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Access forbidden: insufficient permissions."}), 403
                # Render 403 page with HTTP 403 status code
                return render_template("403.html", user_role=current_user.role, allowed_roles=allowed_roles), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Convenience decorator for Administrator-only routes."""
    return role_required(Role.ADMINISTRATOR)(f)


def doctor_required(f):
    """Convenience decorator for Doctor-only routes."""
    return role_required(Role.DOCTOR)(f)


def staff_required(f):
    """Convenience decorator for Staff-only routes."""
    return role_required(Role.STAFF)(f)


def patient_required(f):
    """Convenience decorator for Patient-only routes."""
    return role_required(Role.PATIENT)(f)


def pharmacy_required(f):
    """Convenience decorator for Pharmacy Manager-only routes."""
    return role_required(Role.PHARMACY_MANAGER)(f)
