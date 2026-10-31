from datetime import timedelta
from django.utils import timezone
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room, RoomTypeChoices
from apps.devices.models import Device, RelayChannel, DeviceTypeChoices, DeviceStatusChoices
from apps.telemetry.models import DeviceHeartbeat

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='admin_iot',
        email='iot_admin@institution.edu',
        password='AdminPassword123!',
        is_staff=True
    )
    StaffProfile.objects.create(
        user=user,
        employee_id='ADM-IOT-01',
        role=RoleChoices.ADMIN
    )
    return user

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='faculty_member',
        email='faculty@institution.edu',
        password='FacultyPassword123!'
    )
    StaffProfile.objects.create(
        user=user,
        employee_id='FAC-EE-09',
        role=RoleChoices.STAFF
    )
    return user

@pytest.fixture
def setup_environment(db):
    building = Building.objects.create(name='Computing Block', code='BLD-CS', total_floors=2)
    floor = Floor.objects.create(building=building, level=1, name='1st Floor')
    room_1 = Room.objects.create(floor=floor, name='Embedded Systems Lab', room_number='CS-101', is_active=True)
    room_2 = Room.objects.create(floor=floor, name='IoT Research Lab', room_number='CS-102', is_active=True)
    room_inactive = Room.objects.create(floor=floor, name='Old Server Room', room_number='CS-000', is_active=False)

    device_1 = Device.objects.create(
        room=room_1,
        name='ESP32 Node CS-101 Main',
        hardware_id='ESP32-NODE-CS101-01',
        device_type=DeviceTypeChoices.ESP32_NODE,
        status=DeviceStatusChoices.ONLINE,
        mac_address='24:6F:28:AB:CD:01',
        ip_address='192.168.1.101',
        firmware_version='v2.4.1'
    )
    ch1 = RelayChannel.objects.create(device=device_1, channel_index=1, label='Ceiling Lights', is_on=False, safety_locked=False)
    ch2 = RelayChannel.objects.create(device=device_1, channel_index=2, label='Exhaust Fan', is_on=True, safety_locked=False)
    ch3_locked = RelayChannel.objects.create(device=device_1, channel_index=3, label='Emergency Power', is_on=True, safety_locked=True)

    # Device 2 has no heartbeats (should have calculated_status='UNKNOWN')
    device_2 = Device.objects.create(
        room=room_2,
        name='ESP32 Node CS-102 Sub',
        hardware_id='ESP32-NODE-CS102-02',
        device_type=DeviceTypeChoices.RELAY_MODULE,
        status=DeviceStatusChoices.ONLINE
    )

    return {
        'building': building,
        'floor': floor,
        'room_1': room_1,
        'room_2': room_2,
        'room_inactive': room_inactive,
        'device_1': device_1,
        'device_2': device_2,
        'ch1': ch1,
        'ch2': ch2,
        'ch3_locked': ch3_locked,
    }


@pytest.mark.django_db
class TestDeviceManagementAPIs:

    def test_admin_can_register_device(self, api_client, admin_user, setup_environment):
        api_client.force_authenticate(user=admin_user)
        room_id = setup_environment['room_1'].id

        payload = {
            'name': 'ESP32 Smart Controller',
            'hardware_id': 'ESP32-CTRL-NEW-99',
            'device_type': DeviceTypeChoices.ESP32_NODE,
            'room': room_id,
            'mac_address': 'AA:BB:CC:DD:EE:FF',
            'ip_address': '192.168.1.150',
            'firmware_version': 'v2.5.0',
            'channels': [
                {'channel_index': 1, 'label': 'Bench Power'},
                {'channel_index': 2, 'label': 'Soldering Station'}
            ]
        }
        response = api_client.post('/api/v1/devices/', payload, format='json')
        assert response.status_code == 201
        assert response.data['hardware_id'] == 'ESP32-CTRL-NEW-99'
        assert Device.objects.filter(hardware_id='ESP32-CTRL-NEW-99').exists()
        device = Device.objects.get(hardware_id='ESP32-CTRL-NEW-99')
        assert device.channels.count() == 2

    def test_duplicate_hardware_id_rejected(self, api_client, admin_user, setup_environment):
        api_client.force_authenticate(user=admin_user)
        existing_id = setup_environment['device_1'].hardware_id

        payload = {
            'name': 'Duplicate Node',
            'hardware_id': existing_id,
            'room': setup_environment['room_1'].id
        }
        response = api_client.post('/api/v1/devices/', payload, format='json')
        assert response.status_code == 400
        assert 'hardware_id' in response.data

    def test_staff_cannot_register_device(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        payload = {
            'name': 'Unauthorized Node',
            'hardware_id': 'ESP32-UNAUTH-01',
            'room': setup_environment['room_1'].id
        }
        response = api_client.post('/api/v1/devices/', payload, format='json')
        assert response.status_code == 403

    def test_list_and_filter_devices(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)

        # Test full list
        response = api_client.get('/api/v1/devices/')
        assert response.status_code == 200
        results = response.data['results']
        assert len(results) >= 2

        # Filter by building_code
        bld_resp = api_client.get('/api/v1/devices/?building_code=BLD-CS')
        assert bld_resp.status_code == 200
        assert len(bld_resp.data['results']) == 2

        # Filter by room_number
        room_resp = api_client.get('/api/v1/devices/?room_number=CS-101')
        assert room_resp.status_code == 200
        assert len(room_resp.data['results']) == 1
        assert room_resp.data['results'][0]['hardware_id'] == 'ESP32-NODE-CS101-01'

    def test_device_detail(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_id = setup_environment['device_1'].id
        response = api_client.get(f'/api/v1/devices/{dev_id}/')
        assert response.status_code == 200
        assert response.data['hardware_id'] == 'ESP32-NODE-CS101-01'
        assert len(response.data['channels']) == 3
        assert response.data['building_code'] == 'BLD-CS'

    def test_status_calculation_unknown_without_heartbeat(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_2 = setup_environment['device_2']
        response = api_client.get(f'/api/v1/devices/{dev_2.id}/')
        assert response.status_code == 200
        # Device 2 has no heartbeats, so calculated_status must be UNKNOWN
        assert response.data['calculated_status'] == 'UNKNOWN'

    def test_status_calculation_online_with_fresh_heartbeat(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_1 = setup_environment['device_1']

        # Insert a heartbeat transmitted 30 seconds ago
        DeviceHeartbeat.objects.create(
            device=dev_1,
            voltage=230.5,
            current=1.2,
            power_watts=276.6,
            wifi_rssi=-58,
            uptime_seconds=3600
        )
        response = api_client.get(f'/api/v1/devices/{dev_1.id}/')
        assert response.status_code == 200
        assert response.data['calculated_status'] == 'ONLINE'
        assert response.data['latest_heartbeat']['voltage'] == 230.5

    def test_device_heartbeat_and_history_endpoints(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_1 = setup_environment['device_1']

        DeviceHeartbeat.objects.create(device=dev_1, voltage=229.0, current=0.5, power_watts=114.5)

        hb_resp = api_client.get(f'/api/v1/devices/{dev_1.id}/heartbeat/')
        assert hb_resp.status_code == 200
        assert hb_resp.data['voltage'] == 229.0
        assert hb_resp.data['calculated_status'] == 'ONLINE'

        hist_resp = api_client.get(f'/api/v1/devices/{dev_1.id}/history/')
        assert hist_resp.status_code == 200
        assert len(hist_resp.data) >= 1

    def test_list_device_relay_channels(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_1 = setup_environment['device_1']
        response = api_client.get(f'/api/v1/devices/{dev_1.id}/channels/')
        assert response.status_code == 200
        assert len(response.data) == 3
        indices = [ch['channel_index'] for ch in response.data]
        assert indices == [1, 2, 3]

    def test_assign_device_to_valid_room(self, api_client, admin_user, setup_environment):
        api_client.force_authenticate(user=admin_user)
        dev_1 = setup_environment['device_1']
        new_room_id = setup_environment['room_2'].id

        response = api_client.patch(f'/api/v1/devices/{dev_1.id}/assign-room/', {
            'room_id': new_room_id
        }, format='json')
        assert response.status_code == 200
        assert response.data['new_room'] == 'CS-102'

        dev_1.refresh_from_db()
        assert dev_1.room_id == new_room_id

    def test_assign_device_to_invalid_or_inactive_room(self, api_client, admin_user, setup_environment):
        api_client.force_authenticate(user=admin_user)
        dev_1 = setup_environment['device_1']

        # Nonexistent room
        bad_resp = api_client.patch(f'/api/v1/devices/{dev_1.id}/assign-room/', {
            'room_id': 99999
        }, format='json')
        assert bad_resp.status_code == 400

        # Inactive room
        inactive_room_id = setup_environment['room_inactive'].id
        inactive_resp = api_client.patch(f'/api/v1/devices/{dev_1.id}/assign-room/', {
            'room_id': inactive_room_id
        }, format='json')
        assert inactive_resp.status_code == 400
        assert 'inactive' in str(inactive_resp.data)

    def test_relay_command_validation_and_no_false_hardware_success(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_1 = setup_environment['device_1']
        ch1 = setup_environment['ch1']
        assert ch1.is_on is False

        # Issue toggle ON command for channel 1
        cmd_resp = api_client.post(f'/api/v1/devices/{dev_1.id}/commands/', {
            'channel_index': 1,
            'target_state': True,
            'reason': 'Manual lab activation'
        }, format='json')

        assert cmd_resp.status_code == 202
        data = cmd_resp.data
        assert data['status'] == 'QUEUED_FOR_DEVICE'
        assert data['hardware_ack_received'] is False
        assert data['requested_state'] == 'ON'
        assert data['current_reported_state'] == 'OFF'

        # Physical honesty check: verify that database channel.is_on was NOT modified prematurely
        ch1.refresh_from_db()
        assert not ch1.is_on

    def test_relay_command_rejection_for_safety_locked_channel(self, api_client, staff_user, setup_environment):
        api_client.force_authenticate(user=staff_user)
        dev_1 = setup_environment['device_1']

        # Channel 3 is marked safety_locked=True (Emergency Power)
        locked_resp = api_client.post(f'/api/v1/devices/{dev_1.id}/commands/', {
            'channel_index': 3,
            'target_state': False
        }, format='json')

        assert locked_resp.status_code == 400
        assert 'safety-locked' in str(locked_resp.data)
