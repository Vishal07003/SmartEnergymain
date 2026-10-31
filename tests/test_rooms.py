import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room, RoomTypeChoices, OccupancyStateChoices

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='admin_officer',
        email='officer@institution.edu',
        password='AdminPassword123!',
        is_staff=True
    )
    StaffProfile.objects.create(
        user=user,
        employee_id='ADM-EST-01',
        role=RoleChoices.ADMIN
    )
    return user

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='staff_faculty',
        email='faculty@institution.edu',
        password='FacultyPassword123!'
    )
    StaffProfile.objects.create(
        user=user,
        employee_id='FAC-CS-02',
        role=RoleChoices.STAFF
    )
    return user

@pytest.fixture
def campus_setup(db):
    building_a = Building.objects.create(
        name='Science & Tech Block',
        code='BLD-ST',
        total_floors=3
    )
    floor_1 = Floor.objects.create(building=building_a, level=1, name='Ground Floor')
    floor_2 = Floor.objects.create(building=building_a, level=2, name='First Floor')

    room_101 = Room.objects.create(
        floor=floor_1,
        name='Embedded Systems Lab',
        room_number='ST-101',
        room_type=RoomTypeChoices.COMPUTER_LAB,
        occupancy_state=OccupancyStateChoices.ACTIVE,
        ml_confidence_score=0.98
    )
    room_102 = Room.objects.create(
        floor=floor_1,
        name='Physics Seminar Hall',
        room_number='ST-102',
        room_type=RoomTypeChoices.SEMINAR_HALL,
        occupancy_state=OccupancyStateChoices.EMPTY,
        ml_confidence_score=0.92
    )
    room_201 = Room.objects.create(
        floor=floor_2,
        name='Classroom 201',
        room_number='ST-201',
        room_type=RoomTypeChoices.CLASSROOM,
        occupancy_state=OccupancyStateChoices.IDLE_TRANSITION,
        ml_confidence_score=0.88
    )

    return {
        'building': building_a,
        'floor_1': floor_1,
        'floor_2': floor_2,
        'room_101': room_101,
        'room_102': room_102,
        'room_201': room_201,
    }


@pytest.mark.django_db
class TestRoomManagementAPIs:

    def test_list_buildings(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get('/api/v1/rooms/buildings/')
        assert response.status_code == 200
        data = response.data['results'] if 'results' in response.data else response.data
        assert len(data) >= 1
        assert data[0]['code'] == 'BLD-ST'
        assert data[0]['floors_count'] == 2
        assert data[0]['rooms_count'] == 3

    def test_building_floors_action(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        building_id = campus_setup['building'].id
        response = api_client.get(f'/api/v1/rooms/buildings/{building_id}/floors/')
        assert response.status_code == 200
        assert len(response.data) == 2
        assert response.data[0]['level'] in [1, 2]

    def test_floor_rooms_action(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        floor_id = campus_setup['floor_1'].id
        response = api_client.get(f'/api/v1/rooms/floors/{floor_id}/rooms/')
        assert response.status_code == 200
        assert len(response.data) == 2
        room_numbers = [r['room_number'] for r in response.data]
        assert 'ST-101' in room_numbers
        assert 'ST-102' in room_numbers

    def test_list_rooms_and_filtering(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        
        # Test filter by occupancy_state=ACTIVE
        response = api_client.get('/api/v1/rooms/?occupancy_state=ACTIVE')
        assert response.status_code == 200
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['room_number'] == 'ST-101'
        assert results[0]['occupancy_state'] == 'ACTIVE'

        # Test filter by building_code
        response_bld = api_client.get('/api/v1/rooms/?building_code=BLD-ST')
        assert response_bld.status_code == 200
        assert len(response_bld.data['results']) == 3

        # Test filter by floor_level
        response_floor = api_client.get('/api/v1/rooms/?floor_level=2')
        assert response_floor.status_code == 200
        assert len(response_floor.data['results']) == 1
        assert response_floor.data['results'][0]['room_number'] == 'ST-201'

    def test_room_search(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get('/api/v1/rooms/?search=Embedded')
        assert response.status_code == 200
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['name'] == 'Embedded Systems Lab'

    def test_room_retrieve_detail(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        room_id = campus_setup['room_101'].id
        response = api_client.get(f'/api/v1/rooms/{room_id}/')
        assert response.status_code == 200
        assert response.data['name'] == 'Embedded Systems Lab'
        assert 'devices' in response.data
        assert 'sensors' in response.data
        assert response.data['building_code'] == 'BLD-ST'

    def test_admin_can_create_building_and_room(self, api_client, admin_user, campus_setup):
        api_client.force_authenticate(user=admin_user)
        
        # Create Building
        bld_resp = api_client.post('/api/v1/rooms/buildings/', {
            'name': 'Innovation Hub',
            'code': 'BLD-IH',
            'total_floors': 2
        }, format='json')
        assert bld_resp.status_code == 201
        new_bld_id = bld_resp.data['id']

        # Create Floor
        floor_resp = api_client.post('/api/v1/rooms/floors/', {
            'building': new_bld_id,
            'level': 1,
            'name': 'Ground Robotics Floor'
        }, format='json')
        assert floor_resp.status_code == 201
        new_floor_id = floor_resp.data['id']

        # Create Room
        room_resp = api_client.post('/api/v1/rooms/', {
            'floor': new_floor_id,
            'name': 'Robotics & Automation Lab',
            'room_number': 'IH-101',
            'room_type': RoomTypeChoices.RESEARCH_LAB,
            'occupancy_state': OccupancyStateChoices.EMPTY
        }, format='json')
        assert room_resp.status_code == 201
        assert room_resp.data['room_number'] == 'IH-101'

    def test_staff_cannot_create_or_delete_room(self, api_client, staff_user, campus_setup):
        api_client.force_authenticate(user=staff_user)
        floor_id = campus_setup['floor_1'].id

        # Staff attempt creation -> 403 Forbidden
        post_resp = api_client.post('/api/v1/rooms/', {
            'floor': floor_id,
            'name': 'Unauthorized Lab',
            'room_number': 'ST-999',
            'room_type': RoomTypeChoices.CLASSROOM
        }, format='json')
        assert post_resp.status_code == 403

        # Staff attempt delete -> 403 Forbidden
        room_id = campus_setup['room_101'].id
        del_resp = api_client.delete(f'/api/v1/rooms/{room_id}/')
        assert del_resp.status_code == 403

