from datetime import datetime, timezone
from sqlalchemy import or_, func
from app import db
from app.models.prescription import Prescription, PrescriptionItem, PrescriptionStatus
from app.models.medicine import Medicine, DosageForm
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User, Role


class PrescriptionService:
    """
    Service layer encapsulating Prescription Management business rules,
    validation, multi-drug transaction handling, search, and status state transitions.
    """

    @classmethod
    def get_prescription_by_id(cls, prescription_id):
        """Retrieves a single prescription record by primary key."""
        if not prescription_id:
            return None
        try:
            return db.session.get(Prescription, int(prescription_id))
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_prescriptions_by_patient(cls, patient_id, status=None, page=1, per_page=10):
        """Retrieves paginated prescription history for a specific patient."""
        if not patient_id:
            return None
        query = Prescription.query.filter_by(patient_id=int(patient_id))
        if status and status in PrescriptionStatus.ALL_STATUSES:
            query = query.filter_by(status=status)
        return query.order_by(Prescription.prescription_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @classmethod
    def get_prescriptions_by_doctor(cls, doctor_id, status=None, search=None, page=1, per_page=10):
        """Retrieves paginated prescriptions authored by a specific doctor."""
        if not doctor_id:
            return None
        query = Prescription.query.filter_by(doctor_id=int(doctor_id))
        if status and status in PrescriptionStatus.ALL_STATUSES:
            query = query.filter_by(status=status)

        if search:
            search_clean = search.strip()
            # Clean possible RX / P prefix if numeric search
            numeric_term = None
            if search_clean.upper().startswith("RX") and search_clean[2:].isdigit():
                numeric_term = int(search_clean[2:])
            elif search_clean.upper().startswith("P") and search_clean[1:].isdigit():
                numeric_term = int(search_clean[1:])
            elif search_clean.isdigit():
                numeric_term = int(search_clean)

            search_filter = or_(
                Prescription.patient.has(Patient.user.has(User.first_name.ilike(f"%{search_clean}%"))),
                Prescription.patient.has(Patient.user.has(User.last_name.ilike(f"%{search_clean}%"))),
                Prescription.items.any(PrescriptionItem.medicine.has(Medicine.name.ilike(f"%{search_clean}%")))
            )
            if numeric_term is not None:
                search_filter = or_(search_filter, Prescription.prescription_id == numeric_term)

            query = query.filter(search_filter)

        return query.order_by(Prescription.prescription_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @classmethod
    def get_all_prescriptions(cls, doctor_id=None, patient_id=None, status=None, medicine_id=None,
                              search=None, start_date=None, end_date=None, page=1, per_page=12):
        """
        Retrieves paginated prescriptions with multi-parameter search and combinable filters.
        """
        query = Prescription.query

        if doctor_id:
            try:
                query = query.filter(Prescription.doctor_id == int(doctor_id))
            except (ValueError, TypeError):
                pass

        if patient_id:
            try:
                query = query.filter(Prescription.patient_id == int(patient_id))
            except (ValueError, TypeError):
                pass

        if status and status in PrescriptionStatus.ALL_STATUSES:
            query = query.filter(Prescription.status == status)

        if medicine_id:
            try:
                query = query.filter(Prescription.items.any(PrescriptionItem.medicine_id == int(medicine_id)))
            except (ValueError, TypeError):
                pass

        if start_date:
            try:
                if isinstance(start_date, str):
                    s_dt = datetime.strptime(start_date.strip()[:10], "%Y-%m-%d")
                else:
                    s_dt = start_date
                query = query.filter(Prescription.prescription_date >= s_dt)
            except (ValueError, TypeError):
                pass

        if end_date:
            try:
                if isinstance(end_date, str):
                    e_dt = datetime.strptime(end_date.strip()[:10] + " 23:59:59", "%Y-%m-%d %H:%M:%S")
                else:
                    e_dt = end_date
                query = query.filter(Prescription.prescription_date <= e_dt)
            except (ValueError, TypeError):
                pass

        if search:
            search_clean = search.strip()
            numeric_term = None
            if search_clean.upper().startswith("RX") and search_clean[2:].isdigit():
                numeric_term = int(search_clean[2:])
            elif search_clean.upper().startswith("P") and search_clean[1:].isdigit():
                numeric_term = int(search_clean[1:])
            elif search_clean.isdigit():
                numeric_term = int(search_clean)

            search_filter = or_(
                Prescription.patient.has(Patient.user.has(User.first_name.ilike(f"%{search_clean}%"))),
                Prescription.patient.has(Patient.user.has(User.last_name.ilike(f"%{search_clean}%"))),
                Prescription.doctor.has(Doctor.user.has(User.first_name.ilike(f"%{search_clean}%"))),
                Prescription.doctor.has(Doctor.user.has(User.last_name.ilike(f"%{search_clean}%"))),
                Prescription.items.any(PrescriptionItem.medicine.has(Medicine.name.ilike(f"%{search_clean}%")))
            )
            if numeric_term is not None:
                search_filter = or_(search_filter, Prescription.prescription_id == numeric_term)

            query = query.filter(search_filter)

        return query.order_by(Prescription.prescription_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @classmethod
    def validate_prescription_data(cls, doctor_id, patient_id, items_data, prescription_date=None, status=None):
        """
        Validates all domain prerequisites, patient eligibility, doctor authorization,
        and prescription item integrity before transaction execution.
        """
        errors = []

        # 1. Doctor validation
        if not doctor_id:
            errors.append("Prescribing doctor is required.")
        else:
            try:
                doctor = db.session.get(Doctor, int(doctor_id))
                if not doctor:
                    errors.append("Prescribing doctor not found.")
                elif not doctor.is_active:
                    errors.append("Prescribing doctor account is inactive.")
            except (ValueError, TypeError):
                errors.append("Invalid doctor identifier.")

        # 2. Patient validation
        if not patient_id:
            errors.append("Patient selection is required.")
        else:
            try:
                patient = db.session.get(Patient, int(patient_id))
                if not patient:
                    errors.append("Patient not found. Create the patient profile before issuing a prescription.")
            except (ValueError, TypeError):
                errors.append("Invalid patient identifier.")

        # 3. Status validation
        if status and status not in PrescriptionStatus.ALL_STATUSES:
            errors.append(f"Invalid prescription status '{status}'. Must be one of: {', '.join(PrescriptionStatus.ALL_STATUSES)}.")

        # 4. Items validation
        if not items_data or not isinstance(items_data, list) or len(items_data) == 0:
            errors.append("At least one medicine is required to create a prescription.")
        else:
            seen_medicine_ids = set()
            valid_items_count = 0

            for idx, item in enumerate(items_data, start=1):
                if not isinstance(item, dict):
                    errors.append(f"Item #{idx} contains invalid structure.")
                    continue

                med_id = item.get("medicine_id")
                dosage = (item.get("dosage") or "").strip()
                frequency = (item.get("frequency") or "").strip()
                duration = (item.get("duration") or "").strip()

                if not med_id:
                    errors.append(f"Medicine selection is required for item #{idx}.")
                    continue

                try:
                    med_id_int = int(med_id)
                except (ValueError, TypeError):
                    errors.append(f"Invalid medicine identifier in item #{idx}.")
                    continue

                if med_id_int in seen_medicine_ids:
                    errors.append(f"Duplicate medicine detected in prescription (Medicine ID {med_id_int}). Please specify total dosage/frequency in a single item entry.")
                seen_medicine_ids.add(med_id_int)

                med = db.session.get(Medicine, med_id_int)
                if not med:
                    errors.append(f"Selected medicine (ID {med_id_int}) not found in hospital formulary.")

                if not dosage:
                    errors.append(f"Dosage is required for medicine item #{idx}.")
                if not frequency:
                    errors.append(f"Frequency is required for medicine item #{idx}.")
                if not duration:
                    errors.append(f"Duration is required for medicine item #{idx}.")

                valid_items_count += 1

            if valid_items_count == 0 and not errors:
                errors.append("At least one valid medicine item is required.")

        return errors

    @classmethod
    def create_prescription(cls, doctor_id, patient_id, items_data, prescription_date=None, notes=None,
                            status=PrescriptionStatus.ACTIVE):
        """
        Creates a new Prescription with child PrescriptionItems atomically in a single transaction.
        Rolls back all changes if any part fails.
        """
        errors = cls.validate_prescription_data(
            doctor_id=doctor_id,
            patient_id=patient_id,
            items_data=items_data,
            prescription_date=prescription_date,
            status=status
        )
        if errors:
            return None, errors

        parsed_date = datetime.now(timezone.utc)
        if prescription_date:
            if isinstance(prescription_date, datetime):
                parsed_date = prescription_date
            elif isinstance(prescription_date, str) and prescription_date.strip():
                try:
                    if len(prescription_date.strip()) == 10:
                        parsed_date = datetime.strptime(prescription_date.strip(), "%Y-%m-%d")
                    else:
                        parsed_date = datetime.fromisoformat(prescription_date.strip())
                except (ValueError, TypeError):
                    parsed_date = datetime.now(timezone.utc)

        try:
            prescription = Prescription(
                patient_id=int(patient_id),
                doctor_id=int(doctor_id),
                prescription_date=parsed_date,
                notes=notes,
                status=status or PrescriptionStatus.ACTIVE
            )
            db.session.add(prescription)
            db.session.flush()  # Generate prescription_id for items

            for item in items_data:
                med_id = int(item["medicine_id"])
                dosage = item.get("dosage", "").strip()
                frequency = item.get("frequency", "").strip()
                duration = item.get("duration", "").strip()
                instructions = (item.get("instructions") or "").strip() or None

                rx_item = PrescriptionItem(
                    prescription_id=prescription.prescription_id,
                    medicine_id=med_id,
                    dosage=dosage,
                    frequency=frequency,
                    duration=duration,
                    instructions=instructions
                )
                db.session.add(rx_item)

            db.session.commit()
            return prescription, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Failed to create prescription due to database error: {str(e)}"]

    @classmethod
    def update_prescription_status(cls, prescription_id, new_status, user):
        """
        Updates prescription status (e.g. Active -> Completed / Cancelled).
        Enforces state transition rules and doctor/admin authorization.
        """
        prescription = cls.get_prescription_by_id(prescription_id)
        if not prescription:
            return None, ["Prescription record not found."]

        if not new_status or new_status not in PrescriptionStatus.ALL_STATUSES:
            return None, [f"Invalid status '{new_status}'. Allowed: {', '.join(PrescriptionStatus.ALL_STATUSES)}."]

        # Authorization check: only Admin or the prescribing Doctor can update status
        is_admin = getattr(user, "role", "") == Role.ADMINISTRATOR
        is_author_doctor = (
            getattr(user, "role", "") == Role.DOCTOR and
            hasattr(user, "doctor_profile") and
            user.doctor_profile and
            user.doctor_profile.doctor_id == prescription.doctor_id
        )

        if not (is_admin or is_author_doctor):
            return None, ["Unauthorized: Only the prescribing doctor or an administrator can update this prescription status."]

        # State transition validation:
        # Allowed: Active -> Completed, Active -> Cancelled
        # Disallowed: Completed -> Active, Cancelled -> Active
        if prescription.status == PrescriptionStatus.COMPLETED and new_status == PrescriptionStatus.ACTIVE:
            return None, ["Cannot reactivate a completed prescription. Create a new prescription record if needed."]

        if prescription.status == PrescriptionStatus.CANCELLED and new_status == PrescriptionStatus.ACTIVE:
            return None, ["Cannot reactivate a cancelled prescription."]

        if prescription.status == new_status:
            return prescription, []

        try:
            prescription.status = new_status
            prescription.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return prescription, []
        except Exception as e:
            db.session.rollback()
            return None, [f"Failed to update prescription status: {str(e)}"]

    @classmethod
    def get_prescription_stats(cls, doctor_id=None, patient_id=None):
        """Aggregates live summary statistics for prescriptions."""
        query = Prescription.query
        if doctor_id:
            query = query.filter_by(doctor_id=int(doctor_id))
        if patient_id:
            query = query.filter_by(patient_id=int(patient_id))

        total = query.count()
        active = query.filter_by(status=PrescriptionStatus.ACTIVE).count()
        completed = query.filter_by(status=PrescriptionStatus.COMPLETED).count()
        cancelled = query.filter_by(status=PrescriptionStatus.CANCELLED).count()

        # Count total medicine items prescribed
        items_query = db.session.query(func.count(PrescriptionItem.prescription_item_id)).join(Prescription)
        if doctor_id:
            items_query = items_query.filter(Prescription.doctor_id == int(doctor_id))
        if patient_id:
            items_query = items_query.filter(Prescription.patient_id == int(patient_id))
        total_items = items_query.scalar() or 0

        return {
            "total": total,
            "active": active,
            "completed": completed,
            "cancelled": cancelled,
            "total_items": total_items
        }

    @classmethod
    def get_all_medicines(cls):
        """Retrieves list of all available medicines ordered by name."""
        return Medicine.query.order_by(Medicine.name.asc()).all()

    @classmethod
    def get_or_create_medicine(cls, name, generic_name=None, category=None,
                               dosage_form=DosageForm.TABLET, strength=None, manufacturer=None):
        """Helper to get an existing medicine by name or provision a new one."""
        med_name = name.strip() if name else ""
        if not med_name:
            return None
        medicine = Medicine.query.filter_by(name=med_name).first()
        if not medicine:
            medicine = Medicine(
                name=med_name,
                generic_name=generic_name,
                category=category,
                dosage_form=dosage_form,
                strength=strength,
                manufacturer=manufacturer
            )
            db.session.add(medicine)
            db.session.commit()
        return medicine
