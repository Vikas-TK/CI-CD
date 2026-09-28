import re
from sqlalchemy import or_
from app import db
from app.models.ward import Ward, WardType, WardStatus


class WardService:
    """Service layer encapsulating Ward entity business logic, validation, search, and metrics."""

    @classmethod
    def _validate_ward_name(cls, ward_name, existing_ward_id=None):
        """Validates ward name format and uniqueness."""
        if not ward_name or not str(ward_name).strip():
            return "Ward name is required."

        val = str(ward_name).strip()
        if len(val) > 100:
            return "Ward name must not exceed 100 characters."

        query = Ward.query.filter(Ward.ward_name.ilike(val))
        if existing_ward_id:
            query = query.filter(Ward.ward_id != int(existing_ward_id))

        if query.first():
            return f"Ward name '{val}' already exists."

        return None

    @classmethod
    def _validate_floor(cls, floor):
        """Validates floor number."""
        if floor is None or str(floor).strip() == "":
            return "Floor number is required."
        try:
            val = int(floor)
            if val < -5 or val > 100:
                return "Floor number must be between -5 and 100."
        except (ValueError, TypeError):
            return "Floor must be a valid integer."
        return None

    @classmethod
    def _validate_block(cls, block):
        """Validates building block identifier."""
        if not block or not block.strip():
            return "Building block identifier is required."
        if len(block.strip()) > 50:
            return "Block name must not exceed 50 characters."
        return None

    @classmethod
    def _validate_capacity(cls, capacity):
        """Validates maximum patient/bed capacity (must be positive integer)."""
        if capacity is None or str(capacity).strip() == "":
            return "Ward capacity is required."
        try:
            val = int(capacity)
            if val <= 0:
                return "Ward capacity must be a positive integer greater than 0."
            if val > 1000:
                return "Ward capacity cannot exceed 1000 beds."
        except (ValueError, TypeError):
            return "Ward capacity must be a valid integer."
        return None

    @classmethod
    def validate_ward_data(cls, ward_name, ward_type, floor, block, capacity, status, existing_ward_id=None):
        """Validates ward domain attributes."""
        errors = []

        name_err = cls._validate_ward_name(ward_name, existing_ward_id)
        if name_err:
            errors.append(name_err)

        if not ward_type or not WardType.is_valid(ward_type):
            errors.append(f"Invalid ward type. Must be one of: {', '.join(WardType.ALL_TYPES)}.")

        floor_err = cls._validate_floor(floor)
        if floor_err:
            errors.append(floor_err)

        block_err = cls._validate_block(block)
        if block_err:
            errors.append(block_err)

        cap_err = cls._validate_capacity(capacity)
        if cap_err:
            errors.append(cap_err)

        if not status or not WardStatus.is_valid(status):
            errors.append(f"Invalid ward status. Must be one of: {', '.join(WardStatus.ALL_STATUSES)}.")

        return errors

    @classmethod
    def get_ward_by_id(cls, ward_id):
        """Fetches ward record by primary key."""
        try:
            return db.session.get(Ward, int(ward_id))
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_ward_by_name(cls, ward_name):
        """Fetches ward record by unique ward name."""
        if not ward_name:
            return None
        return Ward.query.filter(Ward.ward_name.ilike(str(ward_name).strip())).first()

    @classmethod
    def create_ward(cls, ward_name, ward_type=WardType.GENERAL, floor=1, block="Block A", capacity=10, status=WardStatus.ACTIVE):
        """Creates a new hospital ward record after thorough validation."""
        errors = cls.validate_ward_data(
            ward_name=ward_name,
            ward_type=ward_type,
            floor=floor,
            block=block,
            capacity=capacity,
            status=status
        )

        if errors:
            return None, errors

        try:
            ward = Ward(
                ward_name=str(ward_name).strip(),
                ward_type=ward_type,
                floor=int(floor),
                block=block.strip(),
                capacity=int(capacity),
                status=status
            )
            db.session.add(ward)
            db.session.commit()
            return ward, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while creating the ward."]

    @classmethod
    def update_ward(cls, ward_id, ward_name=None, ward_type=None, floor=None, block=None, capacity=None, status=None):
        """Updates ward details with safety checks."""
        ward = cls.get_ward_by_id(ward_id)
        if not ward:
            return None, ["Ward record not found."]

        new_name = str(ward_name).strip() if ward_name is not None else ward.ward_name
        new_type = ward_type if ward_type is not None else ward.ward_type
        new_floor = floor if floor is not None else ward.floor
        new_block = block.strip() if block is not None else ward.block
        new_capacity = capacity if capacity is not None else ward.capacity
        new_status = status if status is not None else ward.status

        errors = cls.validate_ward_data(
            ward_name=new_name,
            ward_type=new_type,
            floor=new_floor,
            block=new_block,
            capacity=new_capacity,
            status=new_status,
            existing_ward_id=ward.ward_id
        )

        if errors:
            return None, errors

        try:
            ward.ward_name = new_name
            ward.ward_type = new_type
            ward.floor = int(new_floor)
            ward.block = new_block
            ward.capacity = int(new_capacity)
            ward.status = new_status
            db.session.commit()
            return ward, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while updating the ward."]

    @classmethod
    def delete_ward(cls, ward_id):
        """Deletes a ward record if it is safe to do so."""
        ward = cls.get_ward_by_id(ward_id)
        if not ward:
            return False, "Ward record not found."

        try:
            db.session.delete(ward)
            db.session.commit()
            return True, f"Ward '{ward.ward_name}' was successfully removed."
        except Exception:
            db.session.rollback()
            return False, "A database error occurred while deleting the ward."

    @classmethod
    def _apply_search_filters(cls, query, search_term):
        """Helper to append multi-field search conditions to ORM query."""
        if not search_term:
            return query
        term = f"%{search_term.strip()}%"
        conditions = [
            Ward.ward_name.ilike(term),
            Ward.ward_type.ilike(term),
            Ward.block.ilike(term),
            Ward.status.ilike(term)
        ]
        if search_term.strip().isdigit() or (search_term.strip().startswith("-") and search_term.strip()[1:].isdigit()):
            conditions.append(Ward.floor == int(search_term.strip()))
            conditions.append(Ward.ward_id == int(search_term.strip()))
        return query.filter(or_(*conditions))

    @classmethod
    def get_all_wards(cls, ward_type=None, status=None, floor=None, block=None, search=None, page=1, per_page=12):
        """Retrieves paginated ward records with combinable database filtering and search."""
        query = Ward.query

        if search and search.strip():
            query = cls._apply_search_filters(query, search.strip())

        if ward_type and WardType.is_valid(ward_type):
            query = query.filter(Ward.ward_type == ward_type)

        if status and WardStatus.is_valid(status):
            query = query.filter(Ward.status == status)

        if floor is not None and str(floor).strip() != "":
            try:
                query = query.filter(Ward.floor == int(floor))
            except (ValueError, TypeError):
                pass

        if block and block.strip():
            query = query.filter(Ward.block.ilike(f"%{block.strip()}%"))

        query = query.order_by(Ward.floor.asc(), Ward.ward_name.asc())
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @classmethod
    def get_ward_stats(cls):
        """Computes live aggregated ward capacity and operational status metrics."""
        total = Ward.query.count()
        active = Ward.query.filter_by(status=WardStatus.ACTIVE).count()
        inactive = Ward.query.filter_by(status=WardStatus.INACTIVE).count()
        maintenance = Ward.query.filter_by(status=WardStatus.MAINTENANCE).count()
        total_beds = db.session.query(db.func.coalesce(db.func.sum(Ward.capacity), 0)).scalar() or 0

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "maintenance": maintenance,
            "total_beds": int(total_beds)
        }

    @classmethod
    def get_unique_floors(cls):
        """Fetches distinct floor numbers for dropdown filtering."""
        floors = db.session.query(Ward.floor).distinct().order_by(Ward.floor.asc()).all()
        return [f[0] for f in floors]

    @classmethod
    def get_unique_blocks(cls):
        """Fetches distinct block names for dropdown filtering."""
        blocks = db.session.query(Ward.block).distinct().order_by(Ward.block.asc()).all()
        return [b[0] for b in blocks]
