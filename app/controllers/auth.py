from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import Role
from app.services.user_service import UserService

auth_bp = Blueprint("auth", __name__)


def is_safe_url(target):
    """Prevents open-redirect attacks by validating redirect URLs."""
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Patient registration view."""
    if current_user.is_authenticated:
        return redirect(url_for(Role.get_dashboard_route(current_user.role)))

    if request.method == "POST":
        first_name = request.form.get("first_name", "")
        last_name = request.form.get("last_name", "")
        email = request.form.get("email", "")
        phone_number = request.form.get("phone_number", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        user, errors = UserService.register_patient(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            password=password,
            confirm_password=confirm_password
        )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "auth/register.html",
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number
            ), 400

        flash("Registration successful! You can now log in to your patient account.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login view for all hospital roles."""
    if current_user.is_authenticated:
        return redirect(url_for(Role.get_dashboard_route(current_user.role)))

    if request.method == "POST":
        identifier = request.form.get("identifier", "")
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember_me"))

        user, error_msg = UserService.authenticate(identifier, password)

        if error_msg:
            flash(error_msg, "danger")
            return render_template("auth/login.html", identifier=identifier), 401

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.full_name}!", "success")

        # Check if next URL is requested and safe
        next_page = request.args.get("next")
        if next_page and is_safe_url(next_page):
            return redirect(next_page)

        # Redirect based on user role
        return redirect(url_for(Role.get_dashboard_route(user.role)))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Logs out the current authenticated user."""
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))
