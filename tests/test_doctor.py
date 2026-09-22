from app.models.user import User, Role
from app.models.doctor import Doctor
from app.services.doctor_service import DoctorService


def test_admin_creates_doctor_profile_and_account_success(client, admin_user):

    """Test 1: Administrator successfully creates a doctor account and profile."""
    client.post("/auth/login", data={"identifier": admin_user.email, "password": "AdminPassword123!"})

    payload = {
        "first_name": "Gregory",
        "last_name": "House",
        "email": "dr.house@hospital.org",
        "phone_number": "+15551234567",
        "password": "DoctorPass123!",
        "specialization": "Neurologist",
        "is_active": "1"
    }

    response = client.post("/admin/doctors/create", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Dr. Gregory House" in response.data
    assert b"Neurologist" in response.data

    user = User.query.filter_by(email="dr.house@hospital.org").first()
    assert user is not None
    assert user.role == Role.DOCTOR

    doctor = Doctor.query.filter_by(user_id=user.user_id).first()
    assert doctor is not None
    assert doctor.specialization == "Neurologist"
    assert doctor.full_name == "Gregory House"


def test_unauthenticated_user_cannot_create_doctor(client):
    """Test 2: Unauthenticated users cannot access doctor creation routes."""
    res_get = client.get("/admin/doctors/create", follow_redirects=False)
    assert res_get.status_code == 302
    assert "/auth/login" in res_get.location

    res_post = client.post("/admin/doctors/create", data={"first_name": "Test"}, follow_redirects=False)
    assert res_post.status_code == 302
    assert "/auth/login" in res_post.location


def test_patient_cannot_create_doctor(client, patient_user):
    """Test 3: Patients cannot access doctor creation endpoints (403 Forbidden)."""
    client.post("/auth/login", data={"identifier": patient_user.email, "password": "PatientPassword123!"})

    res_get = client.get("/admin/doctors/create")
    assert res_get.status_code == 403

    res_post = client.post("/admin/doctors/create", data={"first_name": "Test"})
    assert res_post.status_code == 403


def test_doctor_cannot_create_privileged_doctor_accounts(client, doctor_user):
    """Test 4: Doctors cannot provision new doctor accounts on admin routes."""
    client.post("/auth/login", data={"identifier": doctor_user.email, "password": "DoctorPassword123!"})

    res_get = client.get("/admin/doctors/create")
    assert res_get.status_code == 403

    res_post = client.post("/admin/doctors/create", data={"first_name": "Test"})
    assert res_post.status_code == 403


def test_doctor_profile_creation_invalid_specialization(client, admin_user):
    """Test 5: Validation rejection for empty or invalid specializations."""
    client.post("/auth/login", data={"identifier": admin_user.email, "password": "AdminPassword123!"})

    # Empty specialization
    res_empty = client.post("/admin/doctors/create", data={
        "first_name": "Invalid",
        "last_name": "Doc",
        "email": "invaliddoc1@hospital.org",
        "phone_number": "+15551112233",
        "password": "Password123!",
        "specialization": ""
    })
    assert res_empty.status_code == 400
    assert b"Doctor specialization is required" in res_empty.data

    # Specialization with illegal characters
    res_chars = client.post("/admin/doctors/create", data={
        "first_name": "Invalid",
        "last_name": "Doc",
        "email": "invaliddoc2@hospital.org",
        "phone_number": "+15551112234",
        "password": "Password123!",
        "specialization": "Cardiology <script>alert(1)</script>"
    })
    assert res_chars.status_code == 400
    assert b"Specialization contains invalid characters" in res_chars.data


def test_duplicate_doctor_profile_prevention(admin_user, doctor_user):
    """Test 6: Duplicate doctor profiles for the same user account are rejected."""
    # Create first profile
    doc1, errors1 = DoctorService.create_doctor_profile(
        user_id=doctor_user.user_id,
        specialization="Cardiologist"
    )
    assert doc1 is not None
    assert len(errors1) == 0

    # Attempt to create second profile for same user
    doc2, errors2 = DoctorService.create_doctor_profile(
        user_id=doctor_user.user_id,
        specialization="Dermatologist"
    )
    assert doc2 is None
    assert "Doctor profile already exists for this user account." in errors2


def test_doctor_profile_linked_to_correct_user(doctor_user):
    """Test 7: Doctor profile correctly links to the associated User entity."""
    doctor, errors = DoctorService.create_doctor_profile(
        user_id=doctor_user.user_id,
        specialization="Pediatrician"
    )
    assert doctor is not None
    assert doctor.user_id == doctor_user.user_id
    assert doctor.full_name == doctor_user.full_name
    assert doctor.email == doctor_user.email
    assert doctor.phone_number == doctor_user.phone_number
    assert doctor.role == Role.DOCTOR
    assert doctor.is_active is True


def test_rejection_of_profile_linked_to_non_doctor_account(patient_user, staff_user):
    """Test 8: Rejects creating a doctor profile for non-doctor users (e.g. Patient or Staff)."""
    # Patient
    doc_patient, err_patient = DoctorService.create_doctor_profile(
        user_id=patient_user.user_id,
        specialization="Cardiologist"
    )
    assert doc_patient is None
    assert "Cannot link doctor profile to a non-doctor account." in err_patient

    # Staff
    doc_staff, err_staff = DoctorService.create_doctor_profile(
        user_id=staff_user.user_id,
        specialization="General Physician"
    )
    assert doc_staff is None
    assert "Cannot link doctor profile to a non-doctor account." in err_staff


def test_admin_viewing_doctor_list(client, admin_user, doctor_user):
    """Test 9: Administrator viewing doctor directory list."""
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="ENT Specialist")

    client.post("/auth/login", data={"identifier": admin_user.email, "password": "AdminPassword123!"})
    response = client.get("/admin/doctors")
    assert response.status_code == 200
    assert b"Doctor Management" in response.data
    assert doctor_user.full_name.encode() in response.data
    assert b"ENT Specialist" in response.data


def test_admin_viewing_individual_doctor(client, admin_user, doctor_user):
    """Test 10: Administrator viewing single doctor details."""
    doctor, _ = DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="Ophthalmologist")

    client.post("/auth/login", data={"identifier": admin_user.email, "password": "AdminPassword123!"})
    response = client.get(f"/admin/doctors/{doctor.doctor_id}")
    assert response.status_code == 200
    assert doctor_user.full_name.encode() in response.data
    assert b"Ophthalmologist" in response.data
    assert doctor_user.email.encode() in response.data


def test_admin_updating_doctor_profile(client, admin_user, doctor_user):
    """Test 11: Administrator updating permitted doctor profile information."""
    doctor, _ = DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="Cardiologist")

    client.post("/auth/login", data={"identifier": admin_user.email, "password": "AdminPassword123!"})

    update_payload = {
        "specialization": "Orthopedic Specialist",
        "phone_number": "+15559876543"
    }
    response = client.post(f"/admin/doctors/{doctor.doctor_id}/update", data=update_payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"updated successfully" in response.data

    updated_doc = DoctorService.get_doctor_by_id(doctor.doctor_id)
    assert updated_doc.specialization == "Orthopedic Specialist"
    assert updated_doc.phone_number == "+15559876543"


def test_doctor_viewing_own_profile(client, doctor_user):
    """Test 12: Authenticated doctor viewing their own profile."""
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="General Surgeon")

    client.post("/auth/login", data={"identifier": doctor_user.email, "password": "DoctorPassword123!"})
    response = client.get("/doctor/profile")
    assert response.status_code == 200
    assert b"My Doctor Profile" in response.data
    assert doctor_user.full_name.encode() in response.data
    assert b"General Surgeon" in response.data


def test_doctor_attempting_to_view_another_doctor_private_profile(client, doctor_user, app):
    """Test 13: Doctor visiting /doctor/profile sees only their own profile and cannot tamper with another's."""
    # Create doctor 1 (doctor_user)
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="Cardiologist")

    # Create doctor 2
    with app.app_context():
        from app.services.user_service import UserService
        doc2_user, _ = UserService.create_privileged_user(
            first_name="Second",
            last_name="Doctor",
            email="doc2@hospital.org",
            phone_number="+1000000088",
            password="Doc2Password123!",
            role=Role.DOCTOR
        )
        DoctorService.create_doctor_profile(user_id=doc2_user.user_id, specialization="Dermatologist")

    # Log in as doctor 1
    client.post("/auth/login", data={"identifier": doctor_user.email, "password": "DoctorPassword123!"})
    response = client.get("/doctor/profile")
    assert response.status_code == 200
    assert doctor_user.full_name.encode() in response.data
    assert b"Cardiologist" in response.data
    assert b"Second Doctor" not in response.data


def test_doctor_attempting_to_modify_protected_fields(doctor_user, patient_user):
    """Test 14: Protected fields like user_id and role cannot be modified by doctor update service."""
    doctor, _ = DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="General Physician")
    initial_user_id = doctor.user_id

    # Doctor updating their own profile
    DoctorService.update_doctor_profile(
        doctor_id=doctor.doctor_id,
        updating_user=doctor_user,
        specialization="Radiologist"
    )

    refreshed_doc = DoctorService.get_doctor_by_id(doctor.doctor_id)
    assert refreshed_doc.user_id == initial_user_id
    assert refreshed_doc.user.role == Role.DOCTOR
    assert refreshed_doc.specialization == "Radiologist"

    # Patient attempting to update doctor profile
    res_pat, err_pat = DoctorService.update_doctor_profile(
        doctor_id=doctor.doctor_id,
        updating_user=patient_user,
        specialization="Neurologist"
    )
    assert res_pat is None
    assert "Unauthorized" in err_pat[0]


def test_search_by_doctor_name(doctor_user, app):
    """Test 15: Search doctor query by first or last name."""
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="General Physician")

    with app.app_context():
        from app.services.user_service import UserService
        doc_u2, _ = UserService.create_privileged_user(
            first_name="Alexander",
            last_name="Fleming",
            email="fleming@hospital.org",
            phone_number="+1000000077",
            password="Password123!",
            role=Role.DOCTOR
        )
        DoctorService.create_doctor_profile(user_id=doc_u2.user_id, specialization="Microbiologist")

    results = DoctorService.list_doctors(search_query="Fleming").all()
    assert len(results) == 1
    assert results[0].full_name == "Alexander Fleming"


def test_search_by_specialization(doctor_user):
    """Test 16: Search doctor query by specialization."""
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="Cardiologist")

    results = DoctorService.list_doctors(search_query="Cardio").all()
    assert len(results) == 1
    assert results[0].specialization == "Cardiologist"


def test_filtering_by_specialization(doctor_user, app):
    """Test 17: Filter doctor list by exact specialization."""
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="Cardiologist")

    with app.app_context():
        from app.services.user_service import UserService
        doc_u2, _ = UserService.create_privileged_user(
            first_name="Robert",
            last_name="Koch",
            email="koch@hospital.org",
            phone_number="+1000000076",
            password="Password123!",
            role=Role.DOCTOR
        )
        DoctorService.create_doctor_profile(user_id=doc_u2.user_id, specialization="Pediatrician")

    cardio_docs = DoctorService.list_doctors(specialization_filter="Cardiologist").all()
    assert len(cardio_docs) == 1
    assert cardio_docs[0].specialization == "Cardiologist"

    pedia_docs = DoctorService.list_doctors(specialization_filter="Pediatrician").all()
    assert len(pedia_docs) == 1
    assert pedia_docs[0].specialization == "Pediatrician"


def test_missing_doctor_profile_graceful_handling(client, doctor_user):
    """Test 18: Doctor with missing profile record gets graceful informational screen."""
    # doctor_user does not have a Doctor profile created yet
    client.post("/auth/login", data={"identifier": doctor_user.email, "password": "DoctorPassword123!"})
    response = client.get("/doctor/profile")
    assert response.status_code == 200
    assert b"Doctor Profile Pending" in response.data


def test_unauthorized_access_to_admin_doctor_routes(client, patient_user, staff_user, doctor_user, pharmacy_user):
    """Test 19: Non-admin roles receive 403 Forbidden on administrator doctor endpoints."""
    users = [patient_user, staff_user, doctor_user, pharmacy_user]
    for u in users:
        client.post("/auth/login", data={"identifier": u.email, "password": f"{u.role.capitalize()}Password123!"})
        response = client.get("/admin/doctors")
        assert response.status_code == 403


def test_doctor_directory_access_and_filtering(client, patient_user, doctor_user):
    """Test 20: Doctor directory accessible and filterable across public and patient users."""
    DoctorService.create_doctor_profile(user_id=doctor_user.user_id, specialization="Cardiologist")

    # Public visitor access
    public_res = client.get("/doctors")
    assert public_res.status_code == 200
    assert b"Medical Specialists Directory" in public_res.data
    assert doctor_user.full_name.encode() in public_res.data
    assert b"Cardiologist" in public_res.data

    # Logged-in patient access
    client.post("/auth/login", data={"identifier": patient_user.email, "password": "PatientPassword123!"})
    patient_res = client.get("/doctors?search=Doctor")
    assert patient_res.status_code == 200
    assert doctor_user.full_name.encode() in patient_res.data
