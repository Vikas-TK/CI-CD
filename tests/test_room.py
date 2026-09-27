import pytest
from app import db
from app.models.room import Room, RoomType, RoomStatus
from app.services.room_service import RoomService


def _login(client, email, password):
    client.get("/auth/logout")
    return client.post("/auth/login", data={"identifier": email, "password": password}, follow_redirects=True)


@pytest.fixture
def sample_rooms(app):
    """Populates the database with test rooms of varying types, floors, blocks, and statuses."""
    r1, _ = RoomService.create_room("101", RoomType.SINGLE, "1", "A", RoomStatus.AVAILABLE)
    r2, _ = RoomService.create_room("102", RoomType.DOUBLE, "1", "A", RoomStatus.OCCUPIED)
    r3, _ = RoomService.create_room("201", RoomType.SINGLE, "2", "B", RoomStatus.AVAILABLE)
    r4, _ = RoomService.create_room("202", RoomType.DELUXE, "2", "B", RoomStatus.MAINTENANCE)
    r5, _ = RoomService.create_room("ICU-1", RoomType.ICU, "3", "ICU-Wing", RoomStatus.AVAILABLE)
    return [r1, r2, r3, r4, r5]


# 1. Admin can access room management
def test_admin_can_access_room_management(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms")
    assert response.status_code == 200
    assert b"Hospital Room Management" in response.data
    assert b"101" in response.data


# 2. Staff can view rooms
def test_staff_can_view_rooms(client, staff_user, sample_rooms):
    _login(client, staff_user.email, "StaffPassword123!")
    response = client.get("/staff/rooms")
    assert response.status_code == 200
    assert b"Hospital Room Inventory" in response.data
    assert b"101" in response.data

    # View details as staff
    r1 = sample_rooms[0]
    detail_res = client.get(f"/staff/rooms/{r1.room_id}")
    assert detail_res.status_code == 200
    assert b"Room #" in detail_res.data


# 3. Unauthorized users cannot access admin room management
def test_unauthorized_users_cannot_access_admin_room_management(client, patient_user, doctor_user, staff_user, pharmacy_user):
    # Unauthenticated
    client.get("/auth/logout")
    res_unauth = client.get("/admin/rooms", follow_redirects=False)
    assert res_unauth.status_code == 302
    assert "/auth/login" in res_unauth.location

    # Patient
    _login(client, patient_user.email, "PatientPassword123!")
    assert client.get("/admin/rooms").status_code == 403

    # Doctor
    _login(client, doctor_user.email, "DoctorPassword123!")
    assert client.get("/admin/rooms").status_code == 403

    # Staff
    _login(client, staff_user.email, "StaffPassword123!")
    assert client.get("/admin/rooms").status_code == 403

    # Pharmacy Manager
    _login(client, pharmacy_user.email, "PharmacyPassword123!")
    assert client.get("/admin/rooms").status_code == 403


# 4. Admin can create a room
def test_admin_can_create_room(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "room_number": "305",
        "room_type": RoomType.DELUXE,
        "floor": "3",
        "block": "West Wing",
        "status": RoomStatus.AVAILABLE
    }
    response = client.post("/admin/rooms/create", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Room #305" in response.data

    room = Room.query.filter_by(room_number="305").first()
    assert room is not None
    assert room.room_type == RoomType.DELUXE
    assert room.floor == 3
    assert room.block == "West Wing"
    assert room.status == RoomStatus.AVAILABLE


# 5. Duplicate room ID is rejected
def test_duplicate_room_id_is_rejected(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "room_number": "101",  # Already exists in sample_rooms
        "room_type": RoomType.SINGLE,
        "floor": "1",
        "block": "A",
        "status": RoomStatus.AVAILABLE
    }
    response = client.post("/admin/rooms/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"already exists" in response.data


# 6. Invalid room type is rejected
def test_invalid_room_type_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "room_number": "999",
        "room_type": "Penthouse",  # Invalid type
        "floor": "9",
        "block": "Main",
        "status": RoomStatus.AVAILABLE
    }
    response = client.post("/admin/rooms/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Invalid room type" in response.data


# 7. Invalid room status is rejected
def test_invalid_room_status_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "room_number": "998",
        "room_type": RoomType.SINGLE,
        "floor": "1",
        "block": "Main",
        "status": "Demolished"  # Invalid status
    }
    response = client.post("/admin/rooms/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Invalid room status" in response.data


# 8. Missing floor is rejected
def test_missing_floor_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "room_number": "997",
        "room_type": RoomType.SINGLE,
        "floor": "",  # Empty floor
        "block": "Main",
        "status": RoomStatus.AVAILABLE
    }
    response = client.post("/admin/rooms/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Floor number is required" in response.data


# 9. Missing block is rejected
def test_missing_block_is_rejected(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    payload = {
        "room_number": "996",
        "room_type": RoomType.SINGLE,
        "floor": "1",
        "block": "",  # Empty block
        "status": RoomStatus.AVAILABLE
    }
    response = client.post("/admin/rooms/create", data=payload, follow_redirects=True)
    assert response.status_code == 400
    assert b"Building block identifier is required" in response.data


# 10. Admin can edit a room
def test_admin_can_edit_room(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    r1 = sample_rooms[0]

    payload = {
        "room_number": "101-Modified",
        "room_type": RoomType.DELUXE,
        "floor": "1",
        "block": "Wing-A",
        "status": RoomStatus.MAINTENANCE
    }
    response = client.post(f"/admin/rooms/{r1.room_id}/edit", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"101-Modified" in response.data

    updated = db.session.get(Room, r1.room_id)
    assert updated.room_number == "101-Modified"
    assert updated.room_type == RoomType.DELUXE
    assert updated.status == RoomStatus.MAINTENANCE


# 11. Admin can view room details
def test_admin_can_view_room_details(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    r1 = sample_rooms[0]
    response = client.get(f"/admin/rooms/{r1.room_id}")
    assert response.status_code == 200
    assert b"Room #101" in response.data
    assert b"Single" in response.data


# 12. Staff cannot modify rooms
def test_staff_cannot_modify_rooms(client, staff_user, sample_rooms):
    _login(client, staff_user.email, "StaffPassword123!")
    r1 = sample_rooms[0]

    # Staff cannot create room
    res_create = client.post("/admin/rooms/create", data={"room_number": "888"}, follow_redirects=True)
    assert res_create.status_code == 403

    # Staff cannot edit room
    res_edit = client.post(f"/admin/rooms/{r1.room_id}/edit", data={"room_number": "888"}, follow_redirects=True)
    assert res_edit.status_code == 403

    # Staff cannot delete room
    res_delete = client.post(f"/admin/rooms/{r1.room_id}/delete", follow_redirects=True)
    assert res_delete.status_code == 403


# 13. Search by room ID works
def test_search_by_room_id_works(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms?search=ICU-1")
    assert response.status_code == 200
    assert b"ICU-1" in response.data
    assert b"101" not in response.data


# 14. Search by room type works
def test_search_by_room_type_works(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms?room_type=ICU")
    assert response.status_code == 200
    assert b"ICU-1" in response.data
    assert b"101" not in response.data


# 15. Filter by status works
def test_filter_by_status_works(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms?status=Occupied")
    assert response.status_code == 200
    assert b"102" in response.data
    assert b"101" not in response.data


# 16. Filter by floor works
def test_filter_by_floor_works(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms?floor=2")
    assert response.status_code == 200
    assert b"201" in response.data
    assert b"202" in response.data
    assert b"101" not in response.data


# 17. Filter by block works
def test_filter_by_block_works(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms?block=B")
    assert response.status_code == 200
    assert b"201" in response.data
    assert b"202" in response.data
    assert b"101" not in response.data


# 18. Multiple filters work together
def test_multiple_filters_work_together(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")
    # Type=Single, Floor=2, Status=Available should match only 201
    response = client.get("/admin/rooms?room_type=Single&floor=2&status=Available")
    assert response.status_code == 200
    assert b"#201" in response.data
    assert b"#101" not in response.data
    assert b"#202" not in response.data


# 19. Room counts are correct
def test_room_counts_are_correct(sample_rooms):
    stats = RoomService.get_room_stats()
    assert stats["total"] == 5
    assert stats["available"] == 3  # 101, 201, ICU-1
    assert stats["occupied"] == 1   # 102
    assert stats["maintenance"] == 1  # 202


# 20. Nonexistent room returns appropriate error
def test_nonexistent_room_returns_appropriate_error(client, admin_user):
    _login(client, admin_user.email, "AdminPassword123!")
    response = client.get("/admin/rooms/99999", follow_redirects=True)
    assert response.status_code == 200
    assert b"Room record not found" in response.data


# 21. Unauthorized room modification is rejected
def test_unauthorized_room_modification_is_rejected(client, patient_user, sample_rooms):
    _login(client, patient_user.email, "PatientPassword123!")
    r1 = sample_rooms[0]
    res = client.post(f"/admin/rooms/{r1.room_id}/edit", data={"room_number": "Hack"}, follow_redirects=True)
    assert res.status_code == 403


# 22. Room deletion follows the project's safety rules
def test_room_deletion_follows_project_safety_rules(client, admin_user, sample_rooms):
    _login(client, admin_user.email, "AdminPassword123!")

    # Attempt to delete occupied room (102) -> should be prevented
    occupied_room = sample_rooms[1]
    res_occ = client.post(f"/admin/rooms/{occupied_room.room_id}/delete", follow_redirects=True)
    assert res_occ.status_code == 200
    assert b"currently marked as Occupied" in res_occ.data
    assert db.session.get(Room, occupied_room.room_id) is not None

    # Delete available room (101) -> succeeds
    available_room = sample_rooms[0]
    res_avail = client.post(f"/admin/rooms/{available_room.room_id}/delete", follow_redirects=True)
    assert res_avail.status_code == 200
    assert b"successfully removed" in res_avail.data
    assert db.session.get(Room, available_room.room_id) is None

