from datetime import date, timedelta
from app import db
from app.models.appointment import Appointment, AppointmentStatus
from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService
from app.services.patient_service import PatientService
from app.services.user_service import UserService
from app.models.user import Role


def _login(client, email, password):
    """Helper to authenticate a user on the test client."""
    client.get("/auth/logout", follow_redirects=True)
    return client.post("/auth/login", data={"identifier": email, "password": password}, follow_redirects=True)


def test_patient_books_appointment_success(client, patient_user, patient_profile, doctor_profile):
    """Test 1: Patient successfully books an appointment in PENDING status."""
    _login(client, patient_user.email, "PatientPassword123!")

    future_date = (date.today() + timedelta(days=2)).isoformat()
    payload = {
        "doctor_id": doctor_profile.doctor_id,
        "appointment_date": future_date,
        "appointment_time": "10:00",
        "reason_for_visit": "Frequent headaches and blurry vision in mornings."
    }

    response = client.post("/patient/appointments/request", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Appointment request submitted successfully" in response.data

    appointment = Appointment.query.filter_by(patient_id=patient_profile.patient_id).first()
    assert appointment is not None
    assert appointment.doctor_id == doctor_profile.doctor_id
    assert appointment.status == AppointmentStatus.PENDING
    assert appointment.appointment_time.strftime("%H:%M") == "10:00"


def test_patient_booking_fails_missing_fields(client, patient_user, patient_profile, doctor_profile):
    """Test 2: Patient booking validation fails on missing reason or doctor."""
    _login(client, patient_user.email, "PatientPassword123!")

    future_date = (date.today() + timedelta(days=2)).isoformat()
    payload = {
        "doctor_id": doctor_profile.doctor_id,
        "appointment_date": future_date,
        "appointment_time": "10:00",
        "reason_for_visit": ""
    }

    response = client.post("/patient/appointments/request", data=payload)
    assert response.status_code == 400
    assert b"Reason for visit is required" in response.data


def test_patient_booking_fails_past_date(client, patient_user, patient_profile, doctor_profile):
    """Test 3: Booking fails when requested appointment date is in the past."""
    _login(client, patient_user.email, "PatientPassword123!")

    past_date = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "doctor_id": doctor_profile.doctor_id,
        "appointment_date": past_date,
        "appointment_time": "10:00",
        "reason_for_visit": "Checkup"
    }

    response = client.post("/patient/appointments/request", data=payload)
    assert response.status_code == 400
    assert b"Appointment date cannot be in the past" in response.data


def test_patient_booking_fails_invalid_time(client, patient_user, patient_profile, doctor_profile):
    """Test 4: Booking fails when time string is invalid."""
    _login(client, patient_user.email, "PatientPassword123!")

    future_date = (date.today() + timedelta(days=2)).isoformat()
    payload = {
        "doctor_id": doctor_profile.doctor_id,
        "appointment_date": future_date,
        "appointment_time": "25:99",
        "reason_for_visit": "Checkup"
    }

    response = client.post("/patient/appointments/request", data=payload)
    assert response.status_code == 400
    assert b"Invalid time format" in response.data


def test_patient_booking_fails_invalid_doctor(client, patient_user, patient_profile):
    """Test 5: Booking fails with non-existent doctor ID."""
    _login(client, patient_user.email, "PatientPassword123!")

    future_date = (date.today() + timedelta(days=2)).isoformat()
    payload = {
        "doctor_id": 99999,
        "appointment_date": future_date,
        "appointment_time": "10:00",
        "reason_for_visit": "Checkup"
    }

    response = client.post("/patient/appointments/request", data=payload)
    assert response.status_code == 400
    assert b"Invalid or non-existent doctor" in response.data


def test_doctor_double_booking_conflict(client, patient_user, patient_profile, doctor_profile):
    """Test 6: Booking fails when doctor already has an appointment booked at same date and slot."""
    future_date = (date.today() + timedelta(days=3)).isoformat()

    # Pre-book slot
    AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="11:00",
        reason_for_visit="First visit"
    )

    _login(client, patient_user.email, "PatientPassword123!")

    # Attempt to book exact same slot
    payload = {
        "doctor_id": doctor_profile.doctor_id,
        "appointment_date": future_date,
        "appointment_time": "11:00",
        "reason_for_visit": "Second conflicting request"
    }

    response = client.post("/patient/appointments/request", data=payload)
    assert response.status_code == 400
    assert b"already booked" in response.data


def test_patient_views_own_appointments(client, patient_user, patient_profile, doctor_profile):
    """Test 7: Patient views their appointment list and detailed view."""
    future_date = (date.today() + timedelta(days=4)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="09:30",
        reason_for_visit="Consultation on persistent cough"
    )

    _login(client, patient_user.email, "PatientPassword123!")

    # List view
    res_list = client.get("/patient/appointments")
    assert res_list.status_code == 200
    assert b"Consultation on persistent cough" in res_list.data

    # Detailed view
    res_view = client.get(f"/patient/appointments/{appt.appointment_id}")
    assert res_view.status_code == 200
    assert b"Schedule Details" in res_view.data
    assert b"09:30 AM" in res_view.data


def test_patient_cancels_pending_appointment(client, patient_user, patient_profile, doctor_profile):
    """Test 8: Patient can cancel their own PENDING appointment."""
    future_date = (date.today() + timedelta(days=4)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="14:00",
        reason_for_visit="Knee joint pain"
    )

    _login(client, patient_user.email, "PatientPassword123!")

    res = client.post(f"/patient/appointments/{appt.appointment_id}/cancel", follow_redirects=True)
    assert res.status_code == 200
    assert b"has been cancelled" in res.data

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.CANCELLED


def test_patient_cancels_approved_appointment(client, patient_user, patient_profile, doctor_profile):
    """Test 9: Patient can cancel their own APPROVED appointment."""
    future_date = (date.today() + timedelta(days=4)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="15:00",
        reason_for_visit="Follow-up"
    )
    appt.status = AppointmentStatus.APPROVED
    db.session.commit()

    _login(client, patient_user.email, "PatientPassword123!")

    res = client.post(f"/patient/appointments/{appt.appointment_id}/cancel", follow_redirects=True)
    assert res.status_code == 200

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.CANCELLED


def test_patient_cannot_cancel_completed_appointment(client, patient_user, patient_profile, doctor_profile):
    """Test 10: Patient cannot cancel an appointment that is already COMPLETED."""
    future_date = (date.today() + timedelta(days=4)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="16:00",
        reason_for_visit="Concluded checkup"
    )
    appt.status = AppointmentStatus.COMPLETED
    db.session.commit()

    _login(client, patient_user.email, "PatientPassword123!")

    res = client.post(f"/patient/appointments/{appt.appointment_id}/cancel", follow_redirects=True)
    assert res.status_code == 200
    assert b"Cannot modify an appointment that is already Completed" in res.data

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.COMPLETED


def test_patient_cannot_access_other_patient_appointment(client, patient_user, patient_profile, doctor_profile):
    """Test 11: Patient cannot view or cancel another patient's appointment."""
    # Create second patient
    user2, _ = UserService.register_patient(
        first_name="Bob",
        last_name="Smith",
        email="bob@example.com",
        phone_number="+1000000088",
        password="BobPassword123!",
        confirm_password="BobPassword123!"
    )
    p2, _ = PatientService.create_patient_profile(
        user_id=user2.user_id,
        age=45,
        gender="Male",
        aadhaar_number="987654321098",
        blood_group="A+",
        disease_or_complaint="Asthma",
        emergency_contact_name="Mary Smith",
        emergency_contact_phone="+1000000089",
        address="456 Elm Street"
    )

    future_date = (date.today() + timedelta(days=5)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=p2.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="10:00",
        reason_for_visit="Bob's private consultation"
    )

    # Login as patient_user (not Bob)
    _login(client, patient_user.email, "PatientPassword123!")

    res = client.get(f"/patient/appointments/{appt.appointment_id}", follow_redirects=True)
    assert res.status_code == 200
    assert b"Appointment not found or unauthorized" in res.data


def test_doctor_views_assigned_appointments(client, doctor_user, doctor_profile, patient_profile):
    """Test 12: Doctor views their assigned appointments list and detail view."""
    future_date = (date.today() + timedelta(days=2)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="09:00",
        reason_for_visit="Cardiac rhythm review"
    )

    _login(client, doctor_user.email, "DoctorPassword123!")

    res_list = client.get("/doctor/appointments")
    assert res_list.status_code == 200
    assert b"Cardiac rhythm review" in res_list.data

    res_view = client.get(f"/doctor/appointments/{appt.appointment_id}")
    assert res_view.status_code == 200
    assert b"Patient Profile" in res_view.data


def test_doctor_approves_pending_appointment(client, doctor_user, doctor_profile, patient_profile):
    """Test 13: Doctor approves a PENDING consultation request."""
    future_date = (date.today() + timedelta(days=2)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="11:30",
        reason_for_visit="ECG evaluation"
    )

    _login(client, doctor_user.email, "DoctorPassword123!")

    payload = {"status": "Approved", "review_notes": "Approved for 11:30 AM in Cardiology OPD."}
    res = client.post(f"/doctor/appointments/{appt.appointment_id}/status", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"updated to" in res.data and b"Approved" in res.data

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.APPROVED
    assert updated.review_notes == "Approved for 11:30 AM in Cardiology OPD."


def test_doctor_rejects_pending_appointment(client, doctor_user, doctor_profile, patient_profile):
    """Test 14: Doctor rejects a PENDING appointment with clinical reason."""
    future_date = (date.today() + timedelta(days=2)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="14:00",
        reason_for_visit="Non-cardiac dermatological rash"
    )

    _login(client, doctor_user.email, "DoctorPassword123!")

    payload = {"status": "Rejected", "review_notes": "Please book with Dermatology department."}
    res = client.post(f"/doctor/appointments/{appt.appointment_id}/status", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"updated to" in res.data and b"Rejected" in res.data

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.REJECTED
    assert updated.review_notes == "Please book with Dermatology department."


def test_doctor_completes_approved_appointment(client, doctor_user, doctor_profile, patient_profile):
    """Test 15: Doctor marks an APPROVED appointment as COMPLETED with notes."""
    future_date = (date.today() + timedelta(days=2)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="14:30",
        reason_for_visit="Post-surgery follow-up"
    )
    appt.status = AppointmentStatus.APPROVED
    db.session.commit()

    _login(client, doctor_user.email, "DoctorPassword123!")

    payload = {"status": "Completed", "review_notes": "Consultation done. Patient in good recovery."}
    res = client.post(f"/doctor/appointments/{appt.appointment_id}/status", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"updated to" in res.data and b"Completed" in res.data

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.COMPLETED


def test_doctor_cannot_approve_double_booked_slot(client, doctor_user, doctor_profile, patient_profile):
    """Test 16: Doctor cannot approve an appointment if another is already APPROVED at same slot."""
    future_date = (date.today() + timedelta(days=5)).isoformat()

    # Create approved appointment
    appt1, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="10:00",
        reason_for_visit="First visit"
    )
    appt1.status = AppointmentStatus.APPROVED
    db.session.commit()

    # Force create a second appointment in PENDING for same time
    appt2 = Appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        appointment_date=appt1.appointment_date,
        appointment_time=appt1.appointment_time,
        reason_for_visit="Second conflicting booking",
        status=AppointmentStatus.PENDING
    )
    db.session.add(appt2)
    db.session.commit()

    _login(client, doctor_user.email, "DoctorPassword123!")

    payload = {"status": "Approved", "review_notes": "Attempting approval"}
    res = client.post(f"/doctor/appointments/{appt2.appointment_id}/status", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"already has an approved appointment" in res.data

    updated = Appointment.query.get(appt2.appointment_id)
    assert updated.status == AppointmentStatus.PENDING


def test_doctor_cannot_modify_other_doctor_appointment(client, doctor_user, doctor_profile, patient_profile):
    """Test 17: Doctor cannot access or modify another doctor's appointments."""
    # Create second doctor
    u2, _ = UserService.create_privileged_user(
        first_name="Jane",
        last_name="Watson",
        email="dr.watson@hospital.org",
        phone_number="+1000000077",
        password="WatsonPassword123!",
        role=Role.DOCTOR,
        is_active=True
    )
    doc2, _ = DoctorService.create_doctor_profile(user_id=u2.user_id, specialization="ENT Specialist")

    future_date = (date.today() + timedelta(days=6)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doc2.doctor_id,
        date_input=future_date,
        time_input="11:00",
        reason_for_visit="Ear infection"
    )

    # Login as doctor_user (Cardiologist, not Dr. Watson)
    _login(client, doctor_user.email, "DoctorPassword123!")

    res = client.get(f"/doctor/appointments/{appt.appointment_id}", follow_redirects=True)
    assert res.status_code == 200
    assert b"Appointment not found or unauthorized" in res.data


def test_admin_and_staff_manage_hospital_appointments(client, admin_user, staff_user, patient_profile, doctor_profile):
    """Test 18: Admin and Staff can query hospital-wide appointments with search and filters."""
    future_date = (date.today() + timedelta(days=3)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="15:30",
        reason_for_visit="Hypertension evaluation"
    )

    # Admin access
    _login(client, admin_user.email, "AdminPassword123!")
    res_admin = client.get("/admin/appointments")
    assert res_admin.status_code == 200
    assert b"Hospital Appointment Registry" in res_admin.data
    assert b"Hypertension evaluation" in res_admin.data

    # Staff access
    _login(client, staff_user.email, "StaffPassword123!")
    res_staff = client.get("/staff/appointments")
    assert res_staff.status_code == 200
    assert b"Hospital Appointment Registry" in res_staff.data
    assert b"Hypertension evaluation" in res_staff.data


def test_admin_updates_appointment_status(client, admin_user, patient_profile, doctor_profile):
    """Test 19: Administrator updates appointment status directly."""
    future_date = (date.today() + timedelta(days=3)).isoformat()
    appt, _ = AppointmentService.create_appointment(
        patient_id=patient_profile.patient_id,
        doctor_id=doctor_profile.doctor_id,
        date_input=future_date,
        time_input="16:00",
        reason_for_visit="General consultation"
    )

    _login(client, admin_user.email, "AdminPassword123!")

    payload = {"status": "Approved", "review_notes": "Approved by administrative override."}
    res = client.post(f"/admin/appointments/{appt.appointment_id}/status", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"updated to" in res.data and b"Approved" in res.data

    updated = Appointment.query.get(appt.appointment_id)
    assert updated.status == AppointmentStatus.APPROVED


def test_unauthenticated_appointment_access_redirects(client):
    """Test 20: Unauthenticated access to appointment endpoints redirects to login."""
    res_patient = client.get("/patient/appointments", follow_redirects=False)
    assert res_patient.status_code == 302
    assert "/auth/login" in res_patient.location

    res_doctor = client.get("/doctor/appointments", follow_redirects=False)
    assert res_doctor.status_code == 302
    assert "/auth/login" in res_doctor.location

    res_admin = client.get("/admin/appointments", follow_redirects=False)
    assert res_admin.status_code == 302
    assert "/auth/login" in res_admin.location
