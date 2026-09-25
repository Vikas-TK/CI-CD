import os
from datetime import date, timedelta
import click
from app import db
from app.models.user import User, Role
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.staff import Staff
from app.models.appointment import Appointment, AppointmentStatus
from app.services.user_service import UserService
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.staff_service import StaffService
from app.services.appointment_service import AppointmentService


def _seed_sample_users():
    demo_users = [
        ("Admin", "User", "admin@hospital.org", "+1000000001", "AdminPass123!", Role.ADMINISTRATOR),
        ("Sarah", "Jenkins", "doctor.jenkins@hospital.org", "+1000000002", "DoctorPass123!", Role.DOCTOR),
        ("Mark", "Spencer", "staff.mark@hospital.org", "+1000000003", "StaffPass123!", Role.STAFF),
        ("Alice", "Brown", "patient.alice@example.com", "+1000000004", "PatientPass123!", Role.PATIENT),
        ("David", "Kim", "pharmacy.david@hospital.org", "+1000000005", "PharmacyPass123!", Role.PHARMACY_MANAGER),
    ]
    created = 0
    for fname, lname, email, phone, pwd, role in demo_users:
        if not User.query.filter_by(email=email).first():
            user, _ = UserService.create_privileged_user(
                first_name=fname,
                last_name=lname,
                email=email,
                phone_number=phone,
                password=pwd,
                role=role,
                is_active=True
            )
            if user:
                created += 1
    return created


def _seed_sample_patient():
    alice_user = User.query.filter_by(email="patient.alice@example.com").first()
    if alice_user and not Patient.query.filter_by(user_id=alice_user.user_id).first():
        PatientService.create_patient_profile(
            user_id=alice_user.user_id,
            age=29,
            gender="Female",
            aadhaar_number="123456789012",
            blood_group="O+",
            disease_or_complaint="Seasonal allergies and mild respiratory congestion.",
            emergency_contact_name="Robert Brown",
            emergency_contact_phone="+1000000099",
            address="124 Park Avenue, Metro City"
        )


def _seed_sample_doctor():
    sarah_user = User.query.filter_by(email="doctor.jenkins@hospital.org").first()
    if sarah_user and not Doctor.query.filter_by(user_id=sarah_user.user_id).first():
        DoctorService.create_doctor_profile(
            user_id=sarah_user.user_id,
            specialization="Cardiologist"
        )


def _seed_sample_staff():
    mark_user = User.query.filter_by(email="staff.mark@hospital.org").first()
    if mark_user and not Staff.query.filter_by(user_id=mark_user.user_id).first():
        StaffService.create_staff_profile(
            user_id=mark_user.user_id,
            designation="Nurse",
            aadhaar_number="987654321098"
        )


def _seed_sample_appointments():
    alice_user = User.query.filter_by(email="patient.alice@example.com").first()
    sarah_user = User.query.filter_by(email="doctor.jenkins@hospital.org").first()

    if not alice_user or not sarah_user:
        return

    patient = Patient.query.filter_by(user_id=alice_user.user_id).first()
    doctor = Doctor.query.filter_by(user_id=sarah_user.user_id).first()

    if patient and doctor and Appointment.query.count() == 0:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        next_week = (date.today() + timedelta(days=7)).isoformat()

        AppointmentService.create_appointment(
            patient_id=patient.patient_id,
            doctor_id=doctor.doctor_id,
            date_input=tomorrow,
            time_input="10:00",
            reason_for_visit="Routine cardiac follow-up and blood pressure checkup."
        )

        appt2, _ = AppointmentService.create_appointment(
            patient_id=patient.patient_id,
            doctor_id=doctor.doctor_id,
            date_input=next_week,
            time_input="14:30",
            reason_for_visit="Chest tightness and shortness of breath evaluation."
        )
        if appt2:
            appt2.status = AppointmentStatus.APPROVED
            db.session.commit()


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
        """Seeds sample users, doctors, patients, staff, and appointments for development and evaluation."""
        db.create_all()
        created_count = _seed_sample_users()
        _seed_sample_patient()
        _seed_sample_doctor()
        _seed_sample_staff()
        msg = f"Seeded {created_count} demo user accounts, doctor, patient, staff, and appointments."
        click.echo(click.style(msg, fg="green"))
