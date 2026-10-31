import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room
from apps.devices.models import Device, DeviceTypeChoices
from apps.sensors.models import Sensor, SensorTypeChoices
from apps.telemetry.models import TelemetryReading

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='sensor_admin',
        email='sensor_admin@institution.edu',
        password='AdminPassword123!',
        is_staff=True
    )
    StaffProfile.objects.create(user=user, employee_id='ADM-SEN-01', role=RoleChoices.ADMIN)
    return user

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='sensor_staff',
        email='sensor_staff@institution.edu',
        password='StaffPassword123!'
    )
    StaffProfile.objects.create(user=user, employee_id='FAC-SEN-02', role=RoleChoices.STAFF)
    return user

@pytest.fixture
def setup_sensors(db):
    building = Building.objects.create(name='Science Block', code='BLD-SC')
    floor = Floor.objects.create(building=building, level=1, name='1st Floor')
    room_1 = Room.objects.create(floor=floor, name='Robotics Lab', room_number='SC-101', is_active=True)
    room_2 = Room.objects.create(floor=floor, name='Computer Lab', room_number='SC-102', is_active=True)
    room_inactive = Room.objects.create(floor=floor, name='Closed Lab', room_number='SC-999', is_active=False)

    device_1 = Device.objects.create(
        room=room_1,
        name='ESP32 Node 1',
        hardware_id='ESP32-SC101-01',
        device_type=DeviceTypeChoices.ESP32_NODE
    )

    sensor_temp = Sensor.objects.create(
        room=room_1,
        device=device_1,
        sensor_type=SensorTypeChoices.TEMPERATURE,
        sensor_model='DHT22',
        unit_of_measurement='°C'
    )
    sensor_lux = Sensor.objects.create(
        room=room_1,
        device=device_1,
        sensor_type=SensorTypeChoices.AMBIENT_LIGHT,
        sensor_model='BH1750',
        unit_of_measurement='Lux'
    )
    sensor_pir = Sensor.objects.create(
        room=room_1,
        device=device_1,
        sensor_type=SensorTypeChoices.PIR_MOTION,
        sensor_model='HC-SR501',
        unit_of_measurement='state'
    )

    return {
        'room_1': room_1,
        'room_2': room_2,
        'room_inactive': room_inactive,
        'device_1': device_1,
        'sensor_temp': sensor_temp,
        'sensor_lux': sensor_lux,
        'sensor_pir': sensor_pir,
    }


@pytest.mark.django_db
class TestSensorManagementAPIs:

    def test_admin_can_register_sensor(self, api_client, admin_user, setup_sensors):
        api_client.force_authenticate(user=admin_user)
        payload = {
            'room': setup_sensors['room_1'].id,
            'device': setup_sensors['device_1'].id,
            'sensor_type': SensorTypeChoices.HUMIDITY,
            'sensor_model': 'DHT22',
            'unit_of_measurement': '%'
        }
        response = api_client.post('/api/v1/sensors/', payload, format='json')
        assert response.status_code == 201
        assert response.data['sensor_type'] == 'HUMIDITY'
        assert Sensor.objects.filter(sensor_type=SensorTypeChoices.HUMIDITY).exists()

    def test_staff_cannot_register_sensor(self, api_client, staff_user, setup_sensors):
        api_client.force_authenticate(user=staff_user)
        payload = {
            'room': setup_sensors['room_1'].id,
            'sensor_type': SensorTypeChoices.HUMIDITY
        }
        response = api_client.post('/api/v1/sensors/', payload, format='json')
        assert response.status_code == 403

    def test_sensor_assignment_to_inactive_room_fails(self, api_client, admin_user, setup_sensors):
        api_client.force_authenticate(user=admin_user)
        payload = {
            'room': setup_sensors['room_inactive'].id,
            'sensor_type': SensorTypeChoices.SOUND_ACOUSTIC
        }
        response = api_client.post('/api/v1/sensors/', payload, format='json')
        assert response.status_code == 400
        assert 'inactive' in str(response.data)

    def test_sensor_device_room_mismatch_fails(self, api_client, admin_user, setup_sensors):
        api_client.force_authenticate(user=admin_user)
        # Device 1 is in room 1, but we specify room 2
        payload = {
            'room': setup_sensors['room_2'].id,
            'device': setup_sensors['device_1'].id,
            'sensor_type': SensorTypeChoices.CURRENT_POWER
        }
        response = api_client.post('/api/v1/sensors/', payload, format='json')
        assert response.status_code == 400
        assert 'device' in response.data

    def test_list_and_filter_sensors(self, api_client, staff_user, setup_sensors):
        api_client.force_authenticate(user=staff_user)

        # Test full list
        resp = api_client.get('/api/v1/sensors/')
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 3

        # Filter by sensor_type
        temp_resp = api_client.get('/api/v1/sensors/?sensor_type=TEMPERATURE')
        assert temp_resp.status_code == 200
        assert len(temp_resp.data['results']) == 1
        assert temp_resp.data['results'][0]['sensor_type'] == 'TEMPERATURE'

    def test_sensor_detail_and_latest_reading(self, api_client, staff_user, setup_sensors):
        api_client.force_authenticate(user=staff_user)
        sensor = setup_sensors['sensor_temp']

        # Add a reading
        TelemetryReading.objects.create(sensor=sensor, value=24.5)

        detail_resp = api_client.get(f'/api/v1/sensors/{sensor.id}/')
        assert detail_resp.status_code == 200
        assert detail_resp.data['latest_reading']['value'] == 24.5

        latest_resp = api_client.get(f'/api/v1/sensors/{sensor.id}/latest/')
        assert latest_resp.status_code == 200
        assert latest_resp.data['value'] == 24.5
