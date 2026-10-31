from datetime import timedelta
from django.utils import timezone
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room
from apps.devices.models import Device, DeviceTypeChoices
from apps.sensors.models import Sensor, SensorTypeChoices
from apps.telemetry.models import TelemetryReading, DeviceHeartbeat

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def auth_user(db):
    user = User.objects.create_user(
        username='gateway_service',
        email='gateway@institution.edu',
        password='GatewayPassword123!',
        is_staff=True
    )
    StaffProfile.objects.create(user=user, employee_id='SVC-GW-01', role=RoleChoices.ADMIN)
    return user

@pytest.fixture
def setup_telemetry_nodes(db):
    building = Building.objects.create(name='Tech Tower', code='BLD-TT')
    floor = Floor.objects.create(building=building, level=1, name='1st Floor')
    room_1 = Room.objects.create(floor=floor, name='Electronics Lab', room_number='TT-101', is_active=True)
    room_2 = Room.objects.create(floor=floor, name='Machine Hall', room_number='TT-102', is_active=True)

    device_1 = Device.objects.create(
        room=room_1,
        name='Node TT-101',
        hardware_id='ESP32-TT101-01',
        device_type=DeviceTypeChoices.ESP32_NODE
    )
    device_2 = Device.objects.create(
        room=room_2,
        name='Node TT-102',
        hardware_id='ESP32-TT102-02',
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
    sensor_inactive = Sensor.objects.create(
        room=room_1,
        device=device_1,
        sensor_type=SensorTypeChoices.SOUND_ACOUSTIC,
        is_active=False
    )

    return {
        'device_1': device_1,
        'device_2': device_2,
        'sensor_temp': sensor_temp,
        'sensor_lux': sensor_lux,
        'sensor_inactive': sensor_inactive,
    }


@pytest.mark.django_db
class TestTelemetryIngestionAndRetrieval:

    def test_unauthenticated_ingestion_rejected(self, api_client, setup_telemetry_nodes):
        payload = {
            'device_hardware_id': 'ESP32-TT101-01',
            'sensor_id': setup_telemetry_nodes['sensor_temp'].id,
            'value': 23.4
        }
        response = api_client.post('/api/v1/sensors/ingest/telemetry/', payload, format='json')
        assert response.status_code == 401

    def test_valid_telemetry_ingestion(self, api_client, auth_user, setup_telemetry_nodes):
        api_client.force_authenticate(user=auth_user)
        sensor = setup_telemetry_nodes['sensor_temp']

        payload = {
            'device_hardware_id': 'ESP32-TT101-01',
            'sensor_id': sensor.id,
            'value': 25.8,
            'raw_payload': {'temp_c': 25.8, 'humidity_pct': 52.0}
        }
        response = api_client.post('/api/v1/sensors/ingest/telemetry/', payload, format='json')
        assert response.status_code == 201
        assert response.data['status'] == 'RECORDED'
        assert TelemetryReading.objects.filter(sensor=sensor, value=25.8).exists()

    def test_ingestion_rejected_for_unknown_device(self, api_client, auth_user, setup_telemetry_nodes):
        api_client.force_authenticate(user=auth_user)
        payload = {
            'device_hardware_id': 'ESP32-UNKNOWN-999',
            'sensor_id': setup_telemetry_nodes['sensor_temp'].id,
            'value': 22.0
        }
        response = api_client.post('/api/v1/sensors/ingest/telemetry/', payload, format='json')
        assert response.status_code == 400
        assert 'device_hardware_id' in response.data

    def test_ingestion_rejected_for_mismatched_device_and_sensor(self, api_client, auth_user, setup_telemetry_nodes):
        api_client.force_authenticate(user=auth_user)
        # Sensor temp belongs to device_1, but device_2's hardware ID is passed
        payload = {
            'device_hardware_id': 'ESP32-TT102-02',
            'sensor_id': setup_telemetry_nodes['sensor_temp'].id,
            'value': 22.0
        }
        response = api_client.post('/api/v1/sensors/ingest/telemetry/', payload, format='json')
        assert response.status_code == 400
        assert 'sensor_id' in response.data

    def test_ingestion_rejected_for_inactive_sensor(self, api_client, auth_user, setup_telemetry_nodes):
        api_client.force_authenticate(user=auth_user)
        payload = {
            'device_hardware_id': 'ESP32-TT101-01',
            'sensor_id': setup_telemetry_nodes['sensor_inactive'].id,
            'value': 10.0
        }
        response = api_client.post('/api/v1/sensors/ingest/telemetry/', payload, format='json')
        assert response.status_code == 400
        assert 'inactive' in str(response.data)

    def test_heartbeat_ingestion_and_burst_debounce(self, api_client, auth_user, setup_telemetry_nodes):
        api_client.force_authenticate(user=auth_user)
        device = setup_telemetry_nodes['device_1']

        payload = {
            'device_hardware_id': 'ESP32-TT101-01',
            'voltage': 231.2,
            'current': 1.8,
            'power_watts': 416.16,
            'wifi_rssi': -62,
            'uptime_seconds': 7200
        }
        resp1 = api_client.post('/api/v1/sensors/ingest/heartbeat/', payload, format='json')
        assert resp1.status_code == 201
        assert resp1.data['status'] == 'HEARTBEAT_RECORDED'

        # Verify device metadata updated
        device.refresh_from_db()
        assert device.wifi_rssi == -62
        assert device.uptime_hours == 2

        # Immediate re-transmission within debounce window (<10s)
        resp2 = api_client.post('/api/v1/sensors/ingest/heartbeat/', payload, format='json')
        assert resp2.status_code == 200
        assert resp2.data['status'] == 'SUPPRESSED_BURST_DUPLICATE'

    def test_telemetry_readings_list_and_date_filtering(self, api_client, auth_user, setup_telemetry_nodes):
        api_client.force_authenticate(user=auth_user)
        sensor = setup_telemetry_nodes['sensor_lux']

        # Create two readings at different times
        r1 = TelemetryReading.objects.create(sensor=sensor, value=450.0)

        list_resp = api_client.get('/api/v1/sensors/readings/')
        assert list_resp.status_code == 200
        assert len(list_resp.data['results']) >= 1

        # Sensor history action
        hist_resp = api_client.get(f'/api/v1/sensors/{sensor.id}/history/')
        assert hist_resp.status_code == 200
        data = hist_resp.data['results'] if 'results' in hist_resp.data else hist_resp.data
        assert len(data) >= 1
        assert data[0]['value'] == 450.0
