import os
import click
from app import db
from app.models.user import User, Role
from app.services.user_service import UserService


def register_cli_commands(app):
    """Registers CLI commands on the Flask application instance."""

    @app.cli.command("init-db")
    def init_db():
        """Initializes the database schema."""
        db.create_all()
        click.echo(click.style("Database tables successfully created.", fg="green"))

    @app.cli.command("create-admin")
    @click.option("--email", default=lambda: os.environ.get("INITIAL_ADMIN_EMAIL", "admin@hospital.org"),
                  help="Admin email address")
    @click.option("--password", default=lambda: os.environ.get("INITIAL_ADMIN_PASSWORD", "AdminPass123!"),
                  help="Admin password")
    @click.option("--first-name", default=lambda: os.environ.get("INITIAL_ADMIN_FIRST_NAME", "System"),
                  help="First name")
    @click.option("--last-name", default=lambda: os.environ.get("INITIAL_ADMIN_LAST_NAME", "Admin"),
                  help="Last name")
    @click.option("--phone", default=lambda: os.environ.get("INITIAL_ADMIN_PHONE", "+1000000001"),
                  help="Phone number")
    def create_admin(email, password, first_name, last_name, phone):
        """CLI command to safely bootstrap the initial Administrator account."""
        db.create_all()

        existing_user = User.query.filter((User.email == email.lower()) | (User.phone_number == phone)).first()
        if existing_user:
            click.echo(click.style(f"Error: A user with email '{email}' or phone '{phone}' already exists.", fg="red"))
            return

        admin, errors = UserService.create_privileged_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone,
            password=password,
            role=Role.ADMINISTRATOR,
            is_active=True
        )

        if errors:
            click.echo(click.style(f"Error creating admin: {', '.join(errors)}", fg="red"))
        else:
            click.echo(click.style(f"Administrator account '{admin.email}' created successfully!", fg="green"))

    @app.cli.command("seed-data")
    def seed_data():
        """Seeds sample users across all 5 roles for development and evaluation."""
        db.create_all()

        demo_users = [
            ("Admin", "User", "admin@hospital.org", "+1000000001", "AdminPass123!", Role.ADMINISTRATOR),
            ("Sarah", "Jenkins", "doctor.jenkins@hospital.org", "+1000000002", "DoctorPass123!", Role.DOCTOR),
            ("Mark", "Spencer", "staff.mark@hospital.org", "+1000000003", "StaffPass123!", Role.STAFF),
            ("Alice", "Brown", "patient.alice@example.com", "+1000000004", "PatientPass123!", Role.PATIENT),
            ("David", "Kim", "pharmacy.david@hospital.org", "+1000000005", "PharmacyPass123!", Role.PHARMACY_MANAGER),
        ]

        created_count = 0
        for fname, lname, email, phone, pwd, role in demo_users:
            if not User.query.filter_by(email=email).first():
                user, errors = UserService.create_privileged_user(
                    first_name=fname,
                    last_name=lname,
                    email=email,
                    phone_number=phone,
                    password=pwd,
                    role=role,
                    is_active=True
                )
                if user:
                    created_count += 1

        click.echo(click.style(f"Seeded {created_count} demo user accounts successfully.", fg="green"))
