from datetime import datetime, timezone
from sqlalchemy import or_, func
from app import db
from app.models.admission import Admission, AdmissionStatus
from app.models.patient import Patient
from app.models.room import Room, RoomStatus
from app.models.ward import Ward, WardStatus


class AdmissionService:
    """Service layer encapsulating Patient Admission and Inpatient Stay business rules, validation, and transitions."""

    @classmethod
    def get_admission_by_id(cls, admission_id):
        """Retrieves a single admission record by primary key."""
        if not admission_id:
            return None
        try:
            return db.session.get(Admission, int(admission_id))
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_active_admission_for_patient(cls, patient_id):
        """Retrieves current active admission for a patient if one exists."""
        if not patient_id:
            return None
        return Admission.query.filter_by(
            patient_id=int(patient_id),
            status=AdmissionStatus.ACTIVE
        ).first()

    @classmethod
    def get_patient_admission_history(cls, patient_id, page=1, per_page=10):
        """Retrieves paginated admission history for a specific patient, ordered by check-in date descending."""
        if not patient_id:
            return None
        return Admission.query.filter_by(patient_id=int(patient_id))\
            .order_by(Admission.check_in_date.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)

    @classmethod
    def get_ward_active_admission_count(cls, ward_id):
        """Returns the number of active patient admissions currently in the given ward."""
        if not ward_id:
            return 0
        return Admission.query.filter_by(
            ward_id=int(ward_id),
            status=AdmissionStatus.ACTIVE
        ).count()

    @classmethod
    def get_ward_occupancy(cls, ward_id):
        """Calculates live bed capacity metrics for a given ward based on active admissions."""
        ward = db.session.get(Ward, int(ward_id)) if ward_id else None
        if not ward:
            return {"capacity": 0, "occupied": 0, "available": 0, "is_full": True}

        occupied = cls.get_ward_active_admission_count(ward.ward_id)
        available = max(0, ward.capacity - occupied)
        return {
            "capacity": ward.capacity,
            "occupied": occupied,
            "available": available,
            "is_full": occupied >= ward.capacity
        }

    @classmethod
    def validate_admission_data(cls, patient_id, room_id, ward_id, check_in_date=None, reason=None):
        """Validates all domain prerequisites and constraints for admitting a patient."""
        errors = []

        # 1. Patient validation
        if not patient_id:
            errors.append("Patient selection is required.")
            patient = None
        else:
            try:
                patient = db.session.get(Patient, int(patient_id))
                if not patient:
                    errors.append("Patient record not found. Create the patient profile before admission.")
                else:
                    active_adm = cls.get_active_admission_for_patient(patient.patient_id)
                    if active_adm:
                        errors.append(
                            f"Patient '{patient.full_name}' already has an active admission (#ADM{active_adm.admission_id:04d} in Room {active_adm.room_number})."
                        )
            except (ValueError, TypeError):
                errors.append("Invalid patient identifier.")
                patient = None

        # 2. Room validation
        if not room_id:
            errors.append("Room selection is required.")
            room = None
        else:
            try:
                room = db.session.get(Room, int(room_id))
                if not room:
                    errors.append("Selected room not found.")
                elif room.status != RoomStatus.AVAILABLE:
                    errors.append(f"Room '{room.room_number}' is not available for admission (current status: {room.status}).")
            except (ValueError, TypeError):
                errors.append("Invalid room identifier.")
                room = None

        # 3. Ward validation
        if not ward_id:
            errors.append("Ward selection is required.")
            ward = None
        else:
            try:
                ward = db.session.get(Ward, int(ward_id))
                if not ward:
                    errors.append("Selected ward not found.")
                elif ward.status != WardStatus.ACTIVE:
                    errors.append(f"Ward '{ward.ward_name}' is not currently active for new admissions (status: {ward.status}).")
                else:
                    occupancy = cls.get_ward_occupancy(ward.ward_id)
                    if occupancy["is_full"]:
                        errors.append(f"Ward '{ward.ward_name}' has reached its maximum bed capacity ({ward.capacity}/{ward.capacity}).")
            except (ValueError, TypeError):
                errors.append("Invalid ward identifier.")
                ward = None

        # 4. Reason validation
        if reason and len(reason.strip()) > 1000:
            errors.append("Reason for admission must not exceed 1000 characters.")

        return errors, patient, room, ward

    @classmethod
    def admit_patient(cls, patient_id, room_id, ward_id, check_in_date=None, reason=None):
        """
        Atomically admits a patient: validates availability, creates Admission record,
        and marks assigned Room as Occupied.
        """
        errors, patient, room, ward = cls.validate_admission_data(
            patient_id=patient_id,
            room_id=room_id,
            ward_id=ward_id,
            check_in_date=check_in_date,
            reason=reason
        )
        if errors:
            return None, errors

        try:
            # Concurrency double check on room & ward
            rechecked_room = db.session.get(Room, int(room_id))
            if rechecked_room.status != RoomStatus.AVAILABLE:
                return None, [f"Room '{rechecked_room.room_number}' was just assigned by another transaction."]

            rechecked_ward = db.session.get(Ward, int(ward_id))
            if cls.get_ward_active_admission_count(rechecked_ward.ward_id) >= rechecked_ward.capacity:
                return None, [f"Ward '{rechecked_ward.ward_name}' was just filled by another transaction."]

            # Parse or default check_in_date
            if isinstance(check_in_date, str) and check_in_date.strip():
                try:
                    parsed_check_in = datetime.fromisoformat(check_in_date.strip())
                except ValueError:
                    parsed_check_in = datetime.now(timezone.utc)
            elif isinstance(check_in_date, datetime):
                parsed_check_in = check_in_date
            else:
                parsed_check_in = datetime.now(timezone.utc)

            # Create admission record
            admission = Admission(
                patient_id=patient.patient_id,
                room_id=room.room_id,
                ward_id=ward.ward_id,
                check_in_date=parsed_check_in,
                status=AdmissionStatus.ACTIVE,
                reason=reason
            )
            db.session.add(admission)

            # Update room status to Occupied
            room.status = RoomStatus.OCCUPIED

            db.session.commit()
            return admission, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred during patient admission. Transaction rolled back."]

    @classmethod
    def discharge_patient(cls, admission_id, check_out_date=None, discharge_notes=None):
        """
        Discharges a patient: records checkout timestamp, updates status to Discharged,
        and releases the associated room to Available.
        """
        admission = cls.get_admission_by_id(admission_id)
        if not admission:
            return None, ["Admission record not found."]

        if admission.status != AdmissionStatus.ACTIVE:
            return None, [f"Cannot discharge admission #{admission.admission_id:04d} with status '{admission.status}'."]

        # Parse or default check_out_date
        if isinstance(check_out_date, str) and check_out_date.strip():
            try:
                parsed_check_out = datetime.fromisoformat(check_out_date.strip())
            except ValueError:
                parsed_check_out = datetime.now(timezone.utc)
        elif isinstance(check_out_date, datetime):
            parsed_check_out = check_out_date
        else:
            parsed_check_out = datetime.now(timezone.utc)

        # Ensure datetime timezone compatibility for comparison
        adm_check_in = admission.check_in_date
        if adm_check_in and adm_check_in.tzinfo is None and parsed_check_out.tzinfo is not None:
            adm_check_in = adm_check_in.replace(tzinfo=timezone.utc)
        elif adm_check_in and adm_check_in.tzinfo is not None and parsed_check_out.tzinfo is None:
            parsed_check_out = parsed_check_out.replace(tzinfo=timezone.utc)

        if parsed_check_out < adm_check_in:
            return None, ["Check-out date/time cannot be earlier than check-in date/time."]

        try:
            admission.status = AdmissionStatus.DISCHARGED
            admission.check_out_date = parsed_check_out
            if discharge_notes:
                admission.discharge_notes = discharge_notes.strip()

            # Release room back to Available if room exists and is currently occupied
            if admission.room and admission.room.status == RoomStatus.OCCUPIED:
                admission.room.status = RoomStatus.AVAILABLE

            db.session.commit()
            return admission, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred during patient discharge. Transaction rolled back."]

    @classmethod
    def cancel_admission(cls, admission_id, reason=None):
        """Cancels an active admission record and releases the allocated room."""
        admission = cls.get_admission_by_id(admission_id)
        if not admission:
            return None, ["Admission record not found."]

        if admission.status != AdmissionStatus.ACTIVE:
            return None, [f"Cannot cancel admission #{admission.admission_id:04d} with status '{admission.status}'."]

        try:
            admission.status = AdmissionStatus.CANCELLED
            admission.check_out_date = datetime.now(timezone.utc)
            if reason:
                admission.discharge_notes = f"Cancelled: {reason.strip()}"

            # Release room
            if admission.room and admission.room.status == RoomStatus.OCCUPIED:
                admission.room.status = RoomStatus.AVAILABLE

            db.session.commit()
            return admission, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred during admission cancellation."]

    @classmethod
    def transfer_patient(cls, admission_id, new_room_id, new_ward_id=None, transfer_notes=None):
        """
        Transfers an active patient to a different room and/or ward.
        Releases previous room and occupies new room atomically.
        """
        admission = cls.get_admission_by_id(admission_id)
        if not admission:
            return None, ["Admission record not found."]

        if admission.status != AdmissionStatus.ACTIVE:
            return None, [f"Cannot transfer patient for inactive admission (status: '{admission.status}')."]

        try:
            target_room = db.session.get(Room, int(new_room_id))
            if not target_room:
                return None, ["Target room not found."]

            if target_room.room_id == admission.room_id and (not new_ward_id or int(new_ward_id) == admission.ward_id):
                return None, ["Target room and ward are identical to the current allocation."]

            if target_room.status != RoomStatus.AVAILABLE:
                return None, [f"Target room '{target_room.room_number}' is not available (status: {target_room.status})."]

            # If new ward is specified, validate ward
            target_ward_id = int(new_ward_id) if new_ward_id else admission.ward_id
            target_ward = db.session.get(Ward, target_ward_id)
            if not target_ward:
                return None, ["Target ward not found."]

            if target_ward.status != WardStatus.ACTIVE:
                return None, [f"Target ward '{target_ward.ward_name}' is not currently active."]

            # If transferring to a different ward, check capacity
            if target_ward.ward_id != admission.ward_id:
                occupancy = cls.get_ward_occupancy(target_ward.ward_id)
                if occupancy["is_full"]:
                    return None, [f"Target ward '{target_ward.ward_name}' has reached capacity."]

            # Atomic transfer
            old_room = admission.room
            if old_room:
                old_room.status = RoomStatus.AVAILABLE

            target_room.status = RoomStatus.OCCUPIED
            admission.room_id = target_room.room_id
            admission.ward_id = target_ward.ward_id

            note_entry = f"Transferred to Room {target_room.room_number} ({target_ward.ward_name}) on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            if transfer_notes:
                note_entry += f": {transfer_notes.strip()}"

            if admission.discharge_notes:
                admission.discharge_notes += f"\n{note_entry}"
            else:
                admission.discharge_notes = note_entry

            db.session.commit()
            return admission, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred during patient transfer. Transaction rolled back."]

    @classmethod
    def _apply_search_filters(cls, query, search_term):
        """Helper to append multi-field search conditions to ORM query."""
        if not search_term:
            return query
        term = f"%{search_term.strip()}%"

        # Search matching Admission ID, Patient name/phone/email, Room number, Ward name, status
        conditions = [
            Admission.status.ilike(term),
            Admission.reason.ilike(term),
            Patient.aadhaar_number.ilike(term),
            Patient.user.has(or_(
                func.concat(db.Model.metadata.tables['users'].c.first_name, ' ', db.Model.metadata.tables['users'].c.last_name).ilike(term),
                db.Model.metadata.tables['users'].c.first_name.ilike(term),
                db.Model.metadata.tables['users'].c.last_name.ilike(term),
                db.Model.metadata.tables['users'].c.email.ilike(term),
                db.Model.metadata.tables['users'].c.phone_number.ilike(term),
            )),
            Room.room_number.ilike(term),
            Ward.ward_name.ilike(term)
        ]

        if search_term.strip().isdigit():
            conditions.append(Admission.admission_id == int(search_term.strip()))
            conditions.append(Admission.patient_id == int(search_term.strip()))

        return query.filter(or_(*conditions))

    @classmethod
    def get_all_admissions(cls, status=None, ward_id=None, room_id=None, patient_id=None,
                           search=None, page=1, per_page=12):
        """Retrieves paginated admission records with combinable filters and search."""
        query = Admission.query.join(Patient).join(Room).join(Ward)

        if search and search.strip():
            query = cls._apply_search_filters(query, search.strip())

        if status and AdmissionStatus.is_valid(status):
            query = query.filter(Admission.status == status)

        if ward_id:
            try:
                query = query.filter(Admission.ward_id == int(ward_id))
            except (ValueError, TypeError):
                pass

        if room_id:
            try:
                query = query.filter(Admission.room_id == int(room_id))
            except (ValueError, TypeError):
                pass

        if patient_id:
            try:
                query = query.filter(Admission.patient_id == int(patient_id))
            except (ValueError, TypeError):
                pass

        query = query.order_by(
            # Active admissions first, then latest check-in
            db.case((Admission.status == AdmissionStatus.ACTIVE, 1), else_=2).asc(),
            Admission.check_in_date.desc()
        )
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @classmethod
    def get_admission_stats(cls):
        """Computes live aggregated admission, room, and ward operational metrics."""
        total = Admission.query.count()
        active = Admission.query.filter_by(status=AdmissionStatus.ACTIVE).count()
        discharged = Admission.query.filter_by(status=AdmissionStatus.DISCHARGED).count()
        cancelled = Admission.query.filter_by(status=AdmissionStatus.CANCELLED).count()

        # Available and occupied rooms
        available_rooms = Room.query.filter_by(status=RoomStatus.AVAILABLE).count()
        occupied_rooms = Room.query.filter_by(status=RoomStatus.OCCUPIED).count()
        maintenance_rooms = Room.query.filter_by(status=RoomStatus.MAINTENANCE).count()

        # Total capacity across active wards
        total_ward_capacity = db.session.query(
            func.coalesce(func.sum(Ward.capacity), 0)
        ).filter(Ward.status == WardStatus.ACTIVE).scalar() or 0

        return {
            "total": total,
            "active": active,
            "discharged": discharged,
            "cancelled": cancelled,
            "available_rooms": available_rooms,
            "occupied_rooms": occupied_rooms,
            "maintenance_rooms": maintenance_rooms,
            "total_ward_capacity": int(total_ward_capacity),
            "available_beds": max(0, int(total_ward_capacity) - active)
        }
