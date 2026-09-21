from app import db
from app.models.user import User, Role
from app.models.patient import Patient
from app.services.user_service import UserService
from app.services.patient_service import PatientService


def test_create_patient_profile_success(client, patient_user):
    """Test successful patient profile creation by authenticated patient."""
    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    payload = {
        "age": "32",
        "gender": "Male",
        "aadhaar_number": "123456789012",
        "blood_group": "B+",
        "disease_or_complaint": "Persistent migraines and fatigue.",
        "emergency_contact_name": "Mary User",
        "emergency_contact_phone": "+15550197777",
        "address": "456 Healthcare Blvd, Suite 100"
    }

    response = client.post("/patient/profile/complete", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your patient profile has been created successfully" in response.data

    patient = Patient.query.filter_by(user_id=patient_user.user_id).first()
    assert patient is not None
    assert patient.age == 32
    assert patient.gender == "Male"
    assert patient.blood_group == "B+"
    assert patient.masked_aadhaar == "XXXX-XXXX-9012"
    assert patient.emergency_contact_name == "Mary User"


def test_create_patient_profile_unauthenticated(client):
    """Test that unauthenticated requests to complete profile are blocked."""
    response = client.get("/patient/profile/complete", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_create_patient_profile_invalid_age_and_aadhaar(client, patient_user):
    """Test validation errors for negative age and invalid Aadhaar numbers."""
    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    # Negative age
    res_age = client.post("/patient/profile/complete", data={
        "age": "-5",
        "aadhaar_number": "123456789012"
    })
    assert res_age.status_code == 400
    assert b"Age must be between 0 and 130 years" in res_age.data

    # Invalid Aadhaar (only 5 digits)
    res_aadhaar = client.post("/patient/profile/complete", data={
        "age": "25",
        "aadhaar_number": "12345"
    })
    assert res_aadhaar.status_code == 400
    assert b"Aadhaar number must be exactly 12 digits" in res_aadhaar.data


def test_duplicate_patient_profile_prevention(client, patient_user):
    """Test that a user cannot create more than one patient profile."""
    # Create first profile
    PatientService.create_patient_profile(
        user_id=patient_user.user_id,
        age=30,
        gender="Male",
        aadhaar_number="123456789012"
    )

    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    # Attempt second profile creation
    res = client.post("/patient/profile/complete", data={"age": "31"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"already have an active patient profile" in res.data
    assert Patient.query.filter_by(user_id=patient_user.user_id).count() == 1


def test_patient_view_own_profile_and_masking(client, patient_user):
    """Test that a patient can view their own profile and Aadhaar is masked."""
    PatientService.create_patient_profile(
        user_id=patient_user.user_id,
        age=40,
        gender="Female",
        aadhaar_number="987654321098",
        blood_group="O+",
        disease_or_complaint="Asthma treatment checkup"
    )

    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    response = client.get("/patient/profile")
    assert response.status_code == 200
    assert b"Patient Healthcare Profile" in response.data
    assert b"XXXX-XXXX-1098" in response.data  # Masked Aadhaar
    assert b"987654321098" not in response.data  # Plaintext Aadhaar not exposed
    assert b"Asthma treatment checkup" in response.data


def test_patient_update_own_permitted_fields(client, patient_user):
    """Test patient successfully updating permitted fields."""
    patient, _ = PatientService.create_patient_profile(
        user_id=patient_user.user_id,
        age=30,
        gender="Male",
        blood_group="A+"
    )

    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    payload = {
        "age": "31",
        "gender": "Male",
        "blood_group": "A+",
        "disease_or_complaint": "Updated symptom notes.",
        "emergency_contact_name": "Emergency Contact Person",
        "emergency_contact_phone": "+15550190000",
        "address": "789 New Address Street",
        "phone_number": "+1000000099"
    }

    response = client.post("/patient/profile/update", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your profile was updated successfully" in response.data

    updated = db.session.get(Patient, patient.patient_id)
    assert updated.age == 31
    assert updated.disease_or_complaint == "Updated symptom notes."
    assert updated.user.phone_number == "+1000000099"


def test_patient_cannot_tamper_protected_fields(client, patient_user, admin_user):
    """Test that patient cannot alter patient_id, user_id, or role during profile updates."""
    patient, _ = PatientService.create_patient_profile(
        user_id=patient_user.user_id,
        age=28
    )

    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    # Attempt to tamper user_id, role, or patient_id
    payload = {
        "patient_id": "9999",
        "user_id": str(admin_user.user_id),
        "role": Role.ADMINISTRATOR,
        "age": "29"
    }

    client.post("/patient/profile/update", data=payload, follow_redirects=True)
    refreshed_user = db.session.get(User, patient_user.user_id)
    refreshed_patient = db.session.get(Patient, patient.patient_id)

    assert refreshed_user.role == Role.PATIENT
    assert refreshed_patient.user_id == patient_user.user_id
    assert refreshed_patient.patient_id == patient.patient_id


def test_patient_cannot_view_or_edit_another_patient(client, patient_user):
    """Test that a Patient cannot access another patient's admin edit endpoint."""
    # Create second patient
    user2, _ = UserService.register_patient(
        first_name="Second",
        last_name="Patient",
        email="second.patient@hospital.org",
        phone_number="+1000000098",
        password="Password123!",
        confirm_password="Password123!"
    )
    patient2, _ = PatientService.create_patient_profile(user_id=user2.user_id, age=45)

    client.post("/auth/login", data={
        "identifier": patient_user.email,
        "password": "PatientPassword123!"
    })

    # Attempting to access admin edit endpoint for patient2
    response = client.get(f"/admin/patients/{patient2.patient_id}/edit")
    assert response.status_code == 403


def test_admin_patient_management_flow(client, admin_user, patient_user):
    """Test administrator listing, viewing, and updating patient profiles."""
    patient, _ = PatientService.create_patient_profile(
        user_id=patient_user.user_id,
        age=35,
        gender="Male",
        aadhaar_number="555566667777",
        blood_group="AB+",
        disease_or_complaint="Hypertension monitoring"
    )

    client.post("/auth/login", data={
        "identifier": admin_user.email,
        "password": "AdminPassword123!"
    })

    # 1. Admin patient directory list
    list_res = client.get("/admin/patients")
    assert list_res.status_code == 200
    assert patient_user.full_name.encode() in list_res.data
    assert b"XXXX-XXXX-7777" in list_res.data

    # 2. Admin search by complaint
    search_res = client.get("/admin/patients?search=Hypertension")
    assert search_res.status_code == 200
    assert patient_user.full_name.encode() in search_res.data

    # 3. Admin patient details view
    view_res = client.get(f"/admin/patients/{patient.patient_id}")
    assert view_res.status_code == 200
    assert b"Patient Record Details" in view_res.data
    assert b"XXXX-XXXX-7777" in view_res.data

    # 4. Admin update patient profile
    update_payload = {
        "age": "36",
        "gender": "Male",
        "blood_group": "AB+",
        "disease_or_complaint": "Hypertension controlled.",
        "phone_number": patient_user.phone_number
    }
    update_res = client.post(f"/admin/patients/{patient.patient_id}/update", data=update_payload, follow_redirects=True)
    assert update_res.status_code == 200
    assert b"updated successfully" in update_res.data

    updated_patient = db.session.get(Patient, patient.patient_id)
    assert updated_patient.age == 36
    assert updated_patient.disease_or_complaint == "Hypertension controlled."


def test_doctor_and_staff_patient_directory_access(client, doctor_user, staff_user, patient_user):
    """Test that Doctor and Staff roles have authorized read-only patient directory access."""
    patient, _ = PatientService.create_patient_profile(
        user_id=patient_user.user_id,
        age=50,
        blood_group="O-"
    )

    # Doctor access
    client.post("/auth/login", data={"identifier": doctor_user.email, "password": "DoctorPassword123!"})
    doc_list = client.get("/doctor/patients")
    assert doc_list.status_code == 200
    assert patient_user.full_name.encode() in doc_list.data

    doc_view = client.get(f"/doctor/patients/{patient.patient_id}")
    assert doc_view.status_code == 200
    client.get("/auth/logout")

    # Staff access
    client.post("/auth/login", data={"identifier": staff_user.email, "password": "StaffPassword123!"})
    staff_list = client.get("/staff/patients")
    assert staff_list.status_code == 200
    assert patient_user.full_name.encode() in staff_list.data

    staff_view = client.get(f"/staff/patients/{patient.patient_id}")
    assert staff_view.status_code == 200


def test_missing_patient_profile_graceful_handling(client, patient_user):
    """Test that visiting /patient/profile without an existing profile prompts completion."""
    client.post("/auth/login", data={"identifier": patient_user.email, "password": "PatientPassword123!"})
    response = client.get("/patient/profile", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have not completed your patient profile yet" in response.data
    assert b"Complete Your Patient Profile" in response.data
