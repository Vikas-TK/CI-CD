import pytest
from datetime import datetime, timezone
from app import db
from app.models.user import User, Role
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.staff import Staff
from app.models.medicine import Medicine, DosageForm
from app.models.prescription import Prescription, PrescriptionItem, PrescriptionStatus
from app.services.user_service import UserService
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.prescription_service import PrescriptionService


@pytest.fixture
def sample_medicines(app):
    """Provisions a set of standard medicines in the test database."""
    med1 = PrescriptionService.get_or_create_medicine(
        name="Paracetamol",
        generic_name="Acetaminophen",
        category="Analgesic",
        dosage_form=DosageForm.TABLET,
        strength="500 mg"
    )
    med2 = PrescriptionService.get_or_create_medicine(
        name="Cetirizine",
        generic_name="Cetirizine HCl",
        category="Antihistamine",
        dosage_form=DosageForm.TABLET,
        strength="10 mg"
    )
    med3 = PrescriptionService.get_or_create_medicine(
        name="Amoxicillin",
        generic_name="Amoxicillin Trihydrate",
        category="Antibiotic",
        dosage_form=DosageForm.CAPSULE,
        strength="250 mg"
    )
    return med1, med2, med3


def login_user_helper(client, email, password):
    """Helper to authenticate a session in the test client."""
    client.get("/auth/logout")
    return client.post(
        "/auth/login",
        data={"identifier": email, "password": password},
        follow_redirects=True
    )


# ==============================================================================
# 1. AUTHORIZED DOCTOR PRESCRIPTION CREATION
# ==============================================================================

def test_authorized_doctor_can_create_prescription(client, doctor_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that an authenticated doctor can create a prescription with valid items."""
    med1, med2, _ = sample_medicines
    login_user_helper(client, doctor_user.email, "DoctorPassword123!")

    response = client.post(
        "/doctor/prescriptions/create",
        data={
            "patient_id": patient_profile.patient_id,
            "prescription_date": "2026-10-04",
            "notes": "Take with meals. Avoid cold water.",
            "medicine_id[]": [str(med1.medicine_id), str(med2.medicine_id)],
            "dosage[]": ["500 mg", "10 mg"],
            "frequency[]": ["2 times/day", "Once at night"],
            "duration[]": ["5 days", "5 days"],
            "instructions[]": ["After meals", "Before bed"]
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"issued successfully" in response.data or b"#RX" in response.data

    rx = Prescription.query.filter_by(doctor_id=doctor_profile.doctor_id).first()
    assert rx is not None
    assert rx.patient_id == patient_profile.patient_id
    assert rx.status == PrescriptionStatus.ACTIVE
    assert len(rx.items) == 2
    assert rx.items[0].medicine_id == med1.medicine_id
    assert rx.items[1].medicine_id == med2.medicine_id


# ==============================================================================
# 2. UNAUTHORIZED USER CANNOT CREATE PRESCRIPTION
# ==============================================================================

def test_unauthorized_user_cannot_create_prescription(client, patient_user, patient_profile, sample_medicines):
    """Verify that a non-doctor user (e.g., patient) cannot access or post to prescription creation endpoint."""
    med1, _, _ = sample_medicines
    login_user_helper(client, patient_user.email, "PatientPassword123!")

    # Attempt GET creation form
    get_res = client.get("/doctor/prescriptions/create", follow_redirects=True)
    assert get_res.status_code in [403, 302, 200]
    assert b"Doctor" not in get_res.data or b"Access restricted" in get_res.data or b"Patient Portal" in get_res.data

    # Attempt POST creation
    post_res = client.post(
        "/doctor/prescriptions/create",
        data={
            "patient_id": patient_profile.patient_id,
            "medicine_id[]": [str(med1.medicine_id)],
            "dosage[]": ["500 mg"],
            "frequency[]": ["2 times/day"],
            "duration[]": ["5 days"]
        },
        follow_redirects=True
    )
    assert post_res.status_code in [403, 302, 200]
    assert Prescription.query.count() == 0


# ==============================================================================
# 3. PATIENT MUST EXIST
# ==============================================================================

def test_patient_must_exist(doctor_profile, sample_medicines):
    """Verify that prescription creation is rejected when patient_id is invalid or non-existent."""
    med1, _, _ = sample_medicines
    items = [{
        "medicine_id": med1.medicine_id,
        "dosage": "500 mg",
        "frequency": "Once daily",
        "duration": "3 days"
    }]
    rx, errors = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=99999,
        items_data=items
    )
    assert rx is None
    assert any("Patient not found" in err or "patient profile" in err for err in errors)


# ==============================================================================
# 4. DOCTOR MUST EXIST
# ==============================================================================

def test_doctor_must_exist(patient_profile, sample_medicines):
    """Verify that prescription creation is rejected when doctor_id is invalid or non-existent."""
    med1, _, _ = sample_medicines
    items = [{
        "medicine_id": med1.medicine_id,
        "dosage": "500 mg",
        "frequency": "Once daily",
        "duration": "3 days"
    }]
    rx, errors = PrescriptionService.create_prescription(
        doctor_id=99999,
        patient_id=patient_profile.patient_id,
        items_data=items
    )
    assert rx is None
    assert any("doctor not found" in err.lower() for err in errors)


# ==============================================================================
# 5. MEDICINE MUST EXIST
# ==============================================================================

def test_medicine_must_exist(doctor_profile, patient_profile):
    """Verify that prescription creation is rejected when a referenced medicine ID does not exist."""
    items = [{
        "medicine_id": 99999,
        "dosage": "500 mg",
        "frequency": "Once daily",
        "duration": "3 days"
    }]
    rx, errors = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=items
    )
    assert rx is None
    assert any("not found in hospital formulary" in err for err in errors)


# ==============================================================================
# 6. AT LEAST ONE MEDICINE IS REQUIRED
# ==============================================================================

def test_at_least_one_medicine_is_required(doctor_profile, patient_profile):
    """Verify that prescription creation is rejected with an empty items list."""
    rx, errors = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[]
    )
    assert rx is None
    assert any("At least one medicine is required" in err for err in errors)


# ==============================================================================
# 7. MULTIPLE MEDICINES CAN BE ADDED
# ==============================================================================

def test_multiple_medicines_can_be_added(doctor_profile, patient_profile, sample_medicines):
    """Verify that a single prescription correctly records multiple line items."""
    med1, med2, med3 = sample_medicines
    items = [
        {"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"},
        {"medicine_id": med2.medicine_id, "dosage": "10 mg", "frequency": "1/day", "duration": "5 days"},
        {"medicine_id": med3.medicine_id, "dosage": "250 mg", "frequency": "3/day", "duration": "7 days"},
    ]
    rx, errors = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=items
    )
    assert errors == []
    assert rx is not None
    assert rx.item_count == 3
    assert len(rx.items) == 3


# ==============================================================================
# 8. DUPLICATE MEDICINE IN ONE PRESCRIPTION IS REJECTED
# ==============================================================================

def test_duplicate_medicine_in_one_prescription_is_rejected(doctor_profile, patient_profile, sample_medicines):
    """Verify that adding the same medicine twice in one prescription is prevented."""
    med1, _, _ = sample_medicines
    items = [
        {"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "Morning", "duration": "5 days"},
        {"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "Evening", "duration": "5 days"}
    ]
    rx, errors = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=items
    )
    assert rx is None
    assert any("Duplicate medicine detected" in err for err in errors)


# ==============================================================================
# 9. PRESCRIPTION ITEM VALIDATION WORKS
# ==============================================================================

def test_prescription_item_validation_works(doctor_profile, patient_profile, sample_medicines):
    """Verify that missing dosage, frequency, or duration fails validation."""
    med1, _, _ = sample_medicines
    # Missing dosage
    items_missing_dosage = [{"medicine_id": med1.medicine_id, "dosage": "", "frequency": "1/day", "duration": "5 days"}]
    _, err1 = PrescriptionService.create_prescription(doctor_profile.doctor_id, patient_profile.patient_id, items_missing_dosage)
    assert any("Dosage is required" in e for e in err1)

    # Missing frequency
    items_missing_freq = [{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "", "duration": "5 days"}]
    _, err2 = PrescriptionService.create_prescription(doctor_profile.doctor_id, patient_profile.patient_id, items_missing_freq)
    assert any("Frequency is required" in e for e in err2)

    # Missing duration
    items_missing_dur = [{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "1/day", "duration": ""}]
    _, err3 = PrescriptionService.create_prescription(doctor_profile.doctor_id, patient_profile.patient_id, items_missing_dur)
    assert any("Duration is required" in e for e in err3)


# ==============================================================================
# 10. PRESCRIPTION TRANSACTION ROLLS BACK ON FAILURE
# ==============================================================================

def test_prescription_transaction_rolls_back_on_failure(doctor_profile, patient_profile, sample_medicines):
    """Verify that if any item in the prescription fails, the entire transaction is rolled back."""
    med1, _, _ = sample_medicines
    # Valid med1 followed by invalid medicine ID
    items = [
        {"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"},
        {"medicine_id": 99999, "dosage": "10 mg", "frequency": "1/day", "duration": "5 days"}
    ]
    initial_rx_count = Prescription.query.count()
    initial_items_count = PrescriptionItem.query.count()

    rx, errors = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=items
    )
    assert rx is None
    assert len(errors) > 0
    assert Prescription.query.count() == initial_rx_count
    assert PrescriptionItem.query.count() == initial_items_count


# ==============================================================================
# 11. DOCTOR CAN VIEW THEIR OWN PRESCRIPTIONS
# ==============================================================================

def test_doctor_can_view_their_own_prescriptions(client, doctor_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that a doctor can view the list of prescriptions they authored."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    login_user_helper(client, doctor_user.email, "DoctorPassword123!")
    response = client.get("/doctor/prescriptions")
    assert response.status_code == 200
    assert f"RX{rx.prescription_id:04d}".encode() in response.data or patient_profile.full_name.encode() in response.data


# ==============================================================================
# 12. DOCTOR CANNOT MODIFY ANOTHER DOCTOR'S PRESCRIPTION
# ==============================================================================

def test_doctor_cannot_modify_another_doctors_prescription(client, app, doctor_profile, patient_profile, sample_medicines):
    """Verify that a doctor cannot update or cancel a prescription issued by another doctor."""
    med1, _, _ = sample_medicines
    # Create another doctor
    doc2_user, _ = UserService.create_privileged_user(
        first_name="Other", last_name="Doctor", email="other.doc@hospital.org",
        phone_number="+1000000098", password="DoctorPassword123!", role=Role.DOCTOR, is_active=True
    )
    doc2_prof, _ = DoctorService.create_doctor_profile(user_id=doc2_user.user_id, specialization="Neurology")

    # Prescription authored by Doctor 1
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    # Login as Doctor 2
    login_user_helper(client, doc2_user.email, "DoctorPassword123!")
    response = client.post(
        f"/doctor/prescriptions/{rx.prescription_id}/status",
        data={"status": "Cancelled"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"unauthorized" in response.data.lower() or b"danger" in response.data.lower()

    # Re-fetch prescription
    db.session.refresh(rx)
    assert rx.status == PrescriptionStatus.ACTIVE


# ==============================================================================
# 13. PATIENT CAN VIEW THEIR OWN PRESCRIPTIONS
# ==============================================================================

def test_patient_can_view_their_own_prescriptions(client, patient_user, patient_profile, doctor_profile, sample_medicines):
    """Verify that a patient can view their own prescription list and instructions."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days", "instructions": "Take after breakfast"}]
    )

    login_user_helper(client, patient_user.email, "PatientPassword123!")
    response = client.get("/patient/prescriptions")
    assert response.status_code == 200
    assert f"RX{rx.prescription_id:04d}".encode() in response.data

    detail_res = client.get(f"/patient/prescriptions/{rx.prescription_id}")
    assert detail_res.status_code == 200
    assert b"Take after breakfast" in detail_res.data


# ==============================================================================
# 14. PATIENT CANNOT VIEW ANOTHER PATIENT'S PRESCRIPTION
# ==============================================================================

def test_patient_cannot_view_another_patients_prescription(client, app, patient_user, patient_profile, doctor_profile, sample_medicines):
    """Verify that a patient cannot access another patient's prescription (tampering with ID in URL)."""
    med1, _, _ = sample_medicines
    # Create patient 2
    p2_user, _ = UserService.register_patient(
        first_name="Other", last_name="Patient", email="other.patient@example.com",
        phone_number="+1000000097", password="PatientPassword123!", confirm_password="PatientPassword123!"
    )
    p2_prof, _ = PatientService.create_patient_profile(user_id=p2_user.user_id, age=40)

    # Prescription issued for Patient 2
    rx_p2, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=p2_prof.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    # Login as Patient 1
    login_user_helper(client, patient_user.email, "PatientPassword123!")
    response = client.get(f"/patient/prescriptions/{rx_p2.prescription_id}", follow_redirects=True)
    assert response.status_code == 200
    assert b"unauthorized" in response.data.lower() or b"not found" in response.data.lower()


# ==============================================================================
# 15. ADMIN CAN VIEW PRESCRIPTIONS
# ==============================================================================

def test_admin_can_view_prescriptions(client, admin_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that an Administrator can access the master prescriptions directory and details."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    login_user_helper(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/prescriptions")
    assert response.status_code == 200
    assert f"RX{rx.prescription_id:04d}".encode() in response.data

    detail_res = client.get(f"/admin/prescriptions/{rx.prescription_id}")
    assert detail_res.status_code == 200
    assert b"Administrator View" in detail_res.data or b"Paracetamol" in detail_res.data


# ==============================================================================
# 16. STAFF CANNOT ACCESS RESTRICTED PRESCRIPTION INFORMATION
# ==============================================================================

def test_staff_cannot_access_restricted_prescription_information(client, staff_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that staff members cannot access doctor prescription creation or admin prescription views."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    login_user_helper(client, staff_user.email, "StaffPassword123!")
    # Attempt to access doctor prescription create
    doc_res = client.get("/doctor/prescriptions/create", follow_redirects=True)
    assert b"Access restricted" in doc_res.data or doc_res.status_code in [403, 302]

    # Attempt to access admin prescriptions
    admin_res = client.get("/admin/prescriptions", follow_redirects=True)
    assert b"Access restricted" in admin_res.data or admin_res.status_code in [403, 302]


# ==============================================================================
# 17. PRESCRIPTION SEARCH WORKS
# ==============================================================================

def test_prescription_search_works(doctor_profile, patient_profile, sample_medicines):
    """Verify that searching prescriptions by patient name, medicine name, or RX# functions correctly."""
    med1, med2, _ = sample_medicines
    rx1, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    # Search by Medicine Name
    res_med = PrescriptionService.get_all_prescriptions(search="Paracetamol")
    assert res_med.total >= 1
    assert rx1 in res_med.items

    # Search by RX ID
    res_id = PrescriptionService.get_all_prescriptions(search=f"RX{rx1.prescription_id:04d}")
    assert res_id.total >= 1
    assert rx1 in res_id.items


# ==============================================================================
# 18. PATIENT FILTER WORKS
# ==============================================================================

def test_patient_filter_works(doctor_profile, patient_profile, sample_medicines):
    """Verify filtering prescriptions by patient_id returns only matching records."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    res = PrescriptionService.get_all_prescriptions(patient_id=patient_profile.patient_id)
    assert res.total >= 1
    for item in res.items:
        assert item.patient_id == patient_profile.patient_id


# ==============================================================================
# 19. DOCTOR FILTER WORKS
# ==============================================================================

def test_doctor_filter_works(doctor_profile, patient_profile, sample_medicines):
    """Verify filtering prescriptions by doctor_id returns only matching records."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    res = PrescriptionService.get_all_prescriptions(doctor_id=doctor_profile.doctor_id)
    assert res.total >= 1
    for item in res.items:
        assert item.doctor_id == doctor_profile.doctor_id


# ==============================================================================
# 20. STATUS FILTER WORKS
# ==============================================================================

def test_status_filter_works(doctor_profile, patient_profile, sample_medicines):
    """Verify filtering prescriptions by status (Active, Completed, Cancelled)."""
    med1, _, _ = sample_medicines
    rx1, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}],
        status=PrescriptionStatus.ACTIVE
    )
    rx2, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}],
        status=PrescriptionStatus.COMPLETED
    )

    active_res = PrescriptionService.get_all_prescriptions(status=PrescriptionStatus.ACTIVE)
    assert rx1 in active_res.items
    assert rx2 not in active_res.items

    completed_res = PrescriptionService.get_all_prescriptions(status=PrescriptionStatus.COMPLETED)
    assert rx2 in completed_res.items
    assert rx1 not in completed_res.items


# ==============================================================================
# 21. MEDICINE SEARCH WORKS
# ==============================================================================

def test_medicine_search_works(doctor_profile, patient_profile, sample_medicines):
    """Verify filtering prescriptions containing a specific medicine_id."""
    med1, med2, _ = sample_medicines
    rx1, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )
    rx2, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med2.medicine_id, "dosage": "10 mg", "frequency": "1/day", "duration": "5 days"}]
    )

    res_med1 = PrescriptionService.get_all_prescriptions(medicine_id=med1.medicine_id)
    assert rx1 in res_med1.items
    assert rx2 not in res_med1.items


# ==============================================================================
# 22. MULTIPLE FILTERS WORK
# ==============================================================================

def test_multiple_filters_work(doctor_profile, patient_profile, sample_medicines):
    """Verify combinable filters (e.g. Doctor + Status + Medicine)."""
    med1, med2, _ = sample_medicines
    rx1, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}],
        status=PrescriptionStatus.ACTIVE
    )

    res = PrescriptionService.get_all_prescriptions(
        doctor_id=doctor_profile.doctor_id,
        status=PrescriptionStatus.ACTIVE,
        medicine_id=med1.medicine_id
    )
    assert rx1 in res.items


# ==============================================================================
# 23. PRESCRIPTION STATUS TRANSITION WORKS
# ==============================================================================

def test_prescription_status_transition_works(admin_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that updating status from Active to Completed or Cancelled succeeds."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    # Transition to Completed
    updated_rx, errors = PrescriptionService.update_prescription_status(
        prescription_id=rx.prescription_id,
        new_status=PrescriptionStatus.COMPLETED,
        user=admin_user
    )
    assert errors == []
    assert updated_rx.status == PrescriptionStatus.COMPLETED


# ==============================================================================
# 24. INVALID STATUS TRANSITION IS REJECTED
# ==============================================================================

def test_invalid_status_transition_is_rejected(admin_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that attempting to reactivate a Completed or Cancelled prescription is rejected."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}],
        status=PrescriptionStatus.COMPLETED
    )

    # Attempt Completed -> Active
    _, errors = PrescriptionService.update_prescription_status(
        prescription_id=rx.prescription_id,
        new_status=PrescriptionStatus.ACTIVE,
        user=admin_user
    )
    assert len(errors) > 0
    assert any("Cannot reactivate a completed prescription" in err for err in errors)


# ==============================================================================
# 25. PRESCRIPTION DETAIL PAGE WORKS
# ==============================================================================

def test_prescription_detail_page_works(client, doctor_user, doctor_profile, patient_profile, sample_medicines):
    """Verify that viewing prescription details renders all medicines, dosage schedule, and patient chart."""
    med1, med2, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[
            {"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2 times/day", "duration": "5 days", "instructions": "Take after meals"},
            {"medicine_id": med2.medicine_id, "dosage": "10 mg", "frequency": "Once daily", "duration": "5 days", "instructions": "Take at night"}
        ],
        notes="Clinical checkup complete."
    )

    login_user_helper(client, doctor_user.email, "DoctorPassword123!")
    response = client.get(f"/doctor/prescriptions/{rx.prescription_id}")
    assert response.status_code == 200
    assert b"Paracetamol" in response.data
    assert b"Cetirizine" in response.data
    assert b"500 mg" in response.data
    assert b"Take after meals" in response.data
    assert b"Clinical checkup complete." in response.data


# ==============================================================================
# 26. UNAUTHORIZED PRESCRIPTION ACCESS IS REJECTED
# ==============================================================================

def test_unauthorized_prescription_access_is_rejected(client, patient_profile, doctor_profile, sample_medicines):
    """Verify that unauthenticated anonymous visitors cannot access prescription routes."""
    med1, _, _ = sample_medicines
    rx, _ = PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"}]
    )

    # Doctor route unauthenticated
    doc_res = client.get(f"/doctor/prescriptions/{rx.prescription_id}")
    assert doc_res.status_code == 302
    assert "/auth/login" in doc_res.headers.get("Location", "")

    # Patient route unauthenticated
    pat_res = client.get(f"/patient/prescriptions/{rx.prescription_id}")
    assert pat_res.status_code == 302
    assert "/auth/login" in pat_res.headers.get("Location", "")

    # Admin route unauthenticated
    adm_res = client.get(f"/admin/prescriptions/{rx.prescription_id}")
    assert adm_res.status_code == 302
    assert "/auth/login" in adm_res.headers.get("Location", "")


# ==============================================================================
# 27. PRESCRIPTION STATS AGGREGATION WORKS
# ==============================================================================

def test_prescription_stats_aggregation_works(doctor_profile, patient_profile, sample_medicines):
    """Verify that prescription metrics (total, active, completed, cancelled, total_items) compute accurately."""
    med1, med2, _ = sample_medicines
    PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[
            {"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "2/day", "duration": "5 days"},
            {"medicine_id": med2.medicine_id, "dosage": "10 mg", "frequency": "1/day", "duration": "5 days"}
        ],
        status=PrescriptionStatus.ACTIVE
    )
    PrescriptionService.create_prescription(
        doctor_id=doctor_profile.doctor_id,
        patient_id=patient_profile.patient_id,
        items_data=[{"medicine_id": med1.medicine_id, "dosage": "500 mg", "frequency": "1/day", "duration": "3 days"}],
        status=PrescriptionStatus.COMPLETED
    )

    stats = PrescriptionService.get_prescription_stats(doctor_id=doctor_profile.doctor_id)
    assert stats["total"] == 2
    assert stats["active"] == 1
    assert stats["completed"] == 1
    assert stats["cancelled"] == 0
    assert stats["total_items"] == 3
