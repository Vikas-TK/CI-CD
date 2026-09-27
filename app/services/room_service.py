import re
from sqlalchemy import or_
from app import db
from app.models.room import Room, RoomType, RoomStatus


class RoomService:
    """Service layer encapsulating Room entity business logic, validation, search, and metrics."""

    @classmethod
    def _validate_room_number(cls, room_number, existing_room_id=None):
        """Validates room number format and uniqueness."""
        if not room_number or not str(room_number).strip():
            return "Room number is required."

        val = str(room_number).strip()
        if len(val) > 20:
            return "Room number must not exceed 20 characters."

        pattern = re.compile(r"^[a-zA-Z0-9\-_]+$")
        if not pattern.match(val):
            return "Room number contains invalid characters (letters, numbers, hyphens allowed)."

        query = Room.query.filter(Room.room_number.ilike(val))
        if existing_room_id:
            query = query.filter(Room.room_id != int(existing_room_id))

        if query.first():
            return f"Room number '{val}' already exists."

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
    def validate_room_data(cls, room_number, room_type, floor, block, status, existing_room_id=None):
        """Validates room domain attributes."""
        errors = []

        num_err = cls._validate_room_number(room_number, existing_room_id)
        if num_err:
            errors.append(num_err)

        if not room_type or not RoomType.is_valid(room_type):
            errors.append(f"Invalid room type. Must be one of: {', '.join(RoomType.ALL_TYPES)}.")

        floor_err = cls._validate_floor(floor)
        if floor_err:
            errors.append(floor_err)

        block_err = cls._validate_block(block)
        if block_err:
            errors.append(block_err)

        if not status or not RoomStatus.is_valid(status):
            errors.append(f"Invalid room status. Must be one of: {', '.join(RoomStatus.ALL_STATUSES)}.")

        return errors

    @classmethod
    def get_room_by_id(cls, room_id):
        """Fetches room record by primary key."""
        try:
            return db.session.get(Room, int(room_id))
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_room_by_number(cls, room_number):
        """Fetches room record by unique room number."""
        if not room_number:
            return None
        return Room.query.filter_by(room_number=str(room_number).strip()).first()

    @classmethod
    def create_room(cls, room_number, room_type=RoomType.SINGLE, floor=1, block="Block A", status=RoomStatus.AVAILABLE):
        """Creates a new hospital room record after thorough validation."""
        errors = cls.validate_room_data(
            room_number=room_number,
            room_type=room_type,
            floor=floor,
            block=block,
            status=status
        )

        if errors:
            return None, errors

        try:
            room = Room(
                room_number=str(room_number).strip(),
                room_type=room_type,
                floor=int(floor),
                block=block.strip(),
                status=status
            )
            db.session.add(room)
            db.session.commit()
            return room, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while creating the room."]

    @classmethod
    def update_room(cls, room_id, room_number=None, room_type=None, floor=None, block=None, status=None):
        """Updates room details with safety checks."""
        room = cls.get_room_by_id(room_id)
        if not room:
            return None, ["Room record not found."]

        new_number = str(room_number).strip() if room_number is not None else room.room_number
        new_type = room_type if room_type is not None else room.room_type
        new_floor = floor if floor is not None else room.floor
        new_block = block.strip() if block is not None else room.block
        new_status = status if status is not None else room.status

        errors = cls.validate_room_data(
            room_number=new_number,
            room_type=new_type,
            floor=new_floor,
            block=new_block,
            status=new_status,
            existing_room_id=room.room_id
        )

        if errors:
            return None, errors

        try:
            room.room_number = new_number
            room.room_type = new_type
            room.floor = int(new_floor)
            room.block = new_block
            room.status = new_status
            db.session.commit()
            return room, []
        except Exception:
            db.session.rollback()
            return None, ["A database error occurred while updating the room."]

    @classmethod
    def delete_room(cls, room_id):
        """Deletes a room if it is currently safe to do so."""
        room = cls.get_room_by_id(room_id)
        if not room:
            return False, "Room record not found."

        if room.status == RoomStatus.OCCUPIED:
            return False, f"Cannot delete Room #{room.room_number} because it is currently marked as Occupied."

        try:
            db.session.delete(room)
            db.session.commit()
            return True, f"Room #{room.room_number} was successfully removed."
        except Exception:
            db.session.rollback()
            return False, "A database error occurred while deleting the room."

    @classmethod
    def _apply_search_filters(cls, query, search_term):
        """Helper to append multi-field search conditions to ORM query."""
        if not search_term:
            return query
        term = f"%{search_term.strip()}%"
        conditions = [
            Room.room_number.ilike(term),
            Room.room_type.ilike(term),
            Room.block.ilike(term),
            Room.status.ilike(term)
        ]
        if search_term.strip().isdigit() or (search_term.strip().startswith("-") and search_term.strip()[1:].isdigit()):
            conditions.append(Room.floor == int(search_term.strip()))
        return query.filter(or_(*conditions))

    @classmethod
    def get_all_rooms(cls, room_type=None, status=None, floor=None, block=None, search=None, page=1, per_page=12):
        """Retrieves paginated room records with combinable database filtering and search."""
        query = Room.query

        if search and search.strip():
            query = cls._apply_search_filters(query, search.strip())

        if room_type and RoomType.is_valid(room_type):
            query = query.filter(Room.room_type == room_type)

        if status and RoomStatus.is_valid(status):
            query = query.filter(Room.status == status)

        if floor is not None and str(floor).strip() != "":
            try:
                query = query.filter(Room.floor == int(floor))
            except (ValueError, TypeError):
                pass

        if block and block.strip():
            query = query.filter(Room.block.ilike(f"%{block.strip()}%"))

        query = query.order_by(Room.floor.asc(), Room.room_number.asc())
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @classmethod
    def get_room_stats(cls):
        """Computes live aggregated room capacity and availability metrics."""
        total = Room.query.count()
        available = Room.query.filter_by(status=RoomStatus.AVAILABLE).count()
        occupied = Room.query.filter_by(status=RoomStatus.OCCUPIED).count()
        maintenance = Room.query.filter_by(status=RoomStatus.MAINTENANCE).count()

        return {
            "total": total,
            "available": available,
            "occupied": occupied,
            "maintenance": maintenance
        }

    @classmethod
    def get_unique_floors(cls):
        """Fetches distinct floor numbers for dropdown filtering."""
        floors = db.session.query(Room.floor).distinct().order_by(Room.floor.asc()).all()
        return [f[0] for f in floors]

    @classmethod
    def get_unique_blocks(cls):
        """Fetches distinct block names for dropdown filtering."""
        blocks = db.session.query(Room.block).distinct().order_by(Room.block.asc()).all()
        return [b[0] for b in blocks]
