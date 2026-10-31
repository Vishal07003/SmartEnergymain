from datetime import date, timedelta
from django.utils import timezone
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room
from apps.devices.models import Device, DeviceTypeChoices
from apps.energy.models import EnergyReading, DailyEnergyAggregation

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='energy_director',
        email='director@institution.edu',
        password='AdminPassword123!',
        is_staff=True
    )
    StaffProfile.objects.create(user=user, employee_id='ADM-EN-01', role=RoleChoices.ADMIN)
    return user

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='facility_manager',
        email='facility@institution.edu',
        password='StaffPassword123!'
    )
    StaffProfile.objects.create(user=user, employee_id='FAC-FM-02', role=RoleChoices.STAFF)
    return user

@pytest.fixture
def energy_setup(db):
    building_a = Building.objects.create(name='Engineering Block A', code='ENG-A', total_floors=2)
    building_b = Building.objects.create(name='Science Block B', code='SCI-B', total_floors=2)

    floor_a = Floor.objects.create(building=building_a, level=1, name='1st Floor')
    floor_b = Floor.objects.create(building=building_b, level=1, name='1st Floor')

    room_1 = Room.objects.create(floor=floor_a, name='Power Systems Lab', room_number='A-101', is_active=True)
    room_2 = Room.objects.create(floor=floor_a, name='Computing Cluster', room_number='A-102', is_active=True)
    room_3 = Room.objects.create(floor=floor_b, name='Physics Lab', room_number='B-101', is_active=True)
    room_inactive = Room.objects.create(floor=floor_a, name='Closed Room', room_number='A-999', is_active=False)

    device_1 = Device.objects.create(
        room=room_1,
        name='Main Panel Meter',
        hardware_id='PM-ENG-A101-01',
        device_type=DeviceTypeChoices.SMART_POWER_SOCKET
    )

    # Seed daily aggregations for analytics
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    DailyEnergyAggregation.objects.create(
        room=room_1,
        date=today,
        total_kwh=12.5,
        peak_power_watts=1500.0,
        saved_kwh_estimate=2.1,
        wasted_kwh_estimate=0.4
    )
    DailyEnergyAggregation.objects.create(
        room=room_1,
        date=yesterday,
        total_kwh=15.0,
        peak_power_watts=1620.0
    )
    DailyEnergyAggregation.objects.create(
        room=room_2,
        date=today,
        total_kwh=25.0,
        peak_power_watts=3200.0
    )
    DailyEnergyAggregation.objects.create(
        room=room_3,
        date=today,
        total_kwh=8.0,
        peak_power_watts=950.0
    )

    return {
        'building_a': building_a,
        'building_b': building_b,
        'room_1': room_1,
        'room_2': room_2,
        'room_3': room_3,
        'room_inactive': room_inactive,
        'device_1': device_1,
    }


@pytest.mark.django_db
class TestEnergyAndAnalyticsAPIs:

    def test_ingest_energy_reading_success(self, api_client, staff_user, energy_setup):
        api_client.force_authenticate(user=staff_user)
        room = energy_setup['room_1']
        device = energy_setup['device_1']

        payload = {
            'room_id': room.id,
            'device_hardware_id': device.hardware_id,
            'voltage_volts': 231.5,
            'current_amps': 4.2,
            'active_power_watts': 972.3,
            'power_factor': 0.98,
            'frequency_hz': 50.1,
            'energy_kwh': 1.45
        }
        response = api_client.post('/api/v1/energy/ingest/', payload, format='json')
        assert response.status_code == 201
        assert response.data['status'] == 'RECORDED'
        assert response.data['room_number'] == 'A-101'
        assert EnergyReading.objects.filter(room=room, active_power_watts=972.3).exists()

    def test_ingest_energy_reading_invalid_room_or_inactive(self, api_client, staff_user, energy_setup):
        api_client.force_authenticate(user=staff_user)

        # Inactive room rejection
        inactive_room = energy_setup['room_inactive']
        inactive_resp = api_client.post('/api/v1/energy/ingest/', {
            'room_id': inactive_room.id,
            'current_amps': 2.0,
            'active_power_watts': 460.0
        }, format='json')
        assert inactive_resp.status_code == 400
        assert 'inactive' in str(inactive_resp.data)

        # Nonexistent room
        bad_resp = api_client.post('/api/v1/energy/ingest/', {
            'room_id': 99999,
            'current_amps': 1.0,
            'active_power_watts': 230.0
        }, format='json')
        assert bad_resp.status_code == 400

    def test_list_and_filter_energy_readings(self, api_client, staff_user, energy_setup):
        api_client.force_authenticate(user=staff_user)
        room = energy_setup['room_1']

        EnergyReading.objects.create(
            room=room,
            voltage_volts=230.0,
            current_amps=2.0,
            active_power_watts=460.0,
            energy_kwh=0.5
        )

        resp = api_client.get('/api/v1/energy/readings/')
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 1

        # Filter by room_number
        room_filter_resp = api_client.get('/api/v1/energy/readings/?room_number=A-101')
        assert room_filter_resp.status_code == 200
        assert len(room_filter_resp.data['results']) >= 1
        assert room_filter_resp.data['results'][0]['room_number'] == 'A-101'

    def test_latest_energy_reading_by_room(self, api_client, staff_user, energy_setup):
        api_client.force_authenticate(user=staff_user)
        room = energy_setup['room_1']

        EnergyReading.objects.create(room=room, active_power_watts=300.0)
        EnergyReading.objects.create(room=room, active_power_watts=550.0)

        response = api_client.get(f'/api/v1/energy/readings/latest-by-room/?room_id={room.id}')
        assert response.status_code == 200
        assert response.data['active_power_watts'] == 550.0

    def test_campus_energy_summary_analytics(self, api_client, staff_user, energy_setup):
        api_client.force_authenticate(user=staff_user)

        response = api_client.get('/api/v1/energy/analytics/summary/?days=7')
        assert response.status_code == 200
        data = response.data
        # room 1 (12.5 + 15.0) + room 2 (25.0) + room 3 (8.0) = 60.5 kWh
        assert data['total_consumption_kwh'] == 60.5
        assert data['peak_power_watts'] == 3200.0
        assert data['active_monitoring_rooms'] == 3
        assert len(data['room_distribution']) >= 2
        assert 'waste_estimate_notice' in data

    def test_building_comparison_analytics(self, api_client, staff_user, energy_setup):
        api_client.force_authenticate(user=staff_user)

        response = api_client.get('/api/v1/energy/analytics/buildings/?days=30')
        assert response.status_code == 200
        assert len(response.data['buildings']) == 2
        codes = [b['building_code'] for b in response.data['buildings']]
        assert 'ENG-A' in codes
        assert 'SCI-B' in codes

    def test_analytics_empty_dataset_handling(self, api_client, staff_user, db):
        api_client.force_authenticate(user=staff_user)

        # Query a non-existent building ID
        response = api_client.get('/api/v1/energy/analytics/summary/?building_id=99999')
        assert response.status_code == 200
        assert response.data['total_consumption_kwh'] == 0.0
        assert response.data['peak_power_watts'] == 0.0
        assert response.data['active_monitoring_rooms'] == 0
        assert response.data['room_distribution'] == []

