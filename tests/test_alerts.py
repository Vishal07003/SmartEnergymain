from datetime import timedelta
from django.utils import timezone
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room, OccupancyStateChoices
from apps.devices.models import Device, DeviceTypeChoices
from apps.sensors.models import Sensor, SensorTypeChoices
from apps.telemetry.models import TelemetryReading
from apps.energy.models import EnergyReading
from apps.alerts.models import AIAlert, AlertSeverityChoices, AlertCategoryChoices
from apps.alerts.services import AnomalyDetectionService

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='alert_admin',
        email='admin@institution.edu',
        password='AdminPassword123!',
        first_name='System',
        last_name='Admin',
        is_staff=True
    )
    StaffProfile.objects.create(user=user, employee_id='ADM-ALT-01', role=RoleChoices.ADMIN)
    return user

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='faculty_staff',
        email='faculty@institution.edu',
        password='StaffPassword123!',
        first_name='Faculty',
        last_name='Member'
    )
    StaffProfile.objects.create(user=user, employee_id='FAC-ALT-02', role=RoleChoices.STAFF)
    return user

@pytest.fixture
def alert_setup(db):
    bld = Building.objects.create(name='Main Tech Block', code='BLD-M')
    floor = Floor.objects.create(building=bld, level=1, name='1st Floor')
    room_1 = Room.objects.create(floor=floor, name='Embedded Systems Lab', room_number='M-101', occupancy_state=OccupancyStateChoices.EMPTY)
    room_2 = Room.objects.create(floor=floor, name='Auditorium', room_number='M-102', occupancy_state=OccupancyStateChoices.ACTIVE)

    device_1 = Device.objects.create(
        room=room_1,
        name='Main Panel',
        hardware_id='ESP32-M101-01',
        device_type=DeviceTypeChoices.ESP32_NODE
    )

    alert_1 = AIAlert.objects.create(
        title="High Wastage in Vacant Room",
        severity=AlertSeverityChoices.HIGH,
        category=AlertCategoryChoices.ENERGY_WASTE,
        room=room_1,
        device=device_1,
        description="HVAC running with no occupants detected.",
        power_wastage_estimate_watts=850.0,
        detection_method="RULE_BASED"
    )

    alert_2 = AIAlert.objects.create(
        title="Critical Power Surge",
        severity=AlertSeverityChoices.CRITICAL,
        category=AlertCategoryChoices.SAFETY_TRIGGER,
        room=room_2,
        description="Active power exceeded safe baseline.",
        power_wastage_estimate_watts=4200.0,
        detection_method="RULE_BASED"
    )

    return {
        'building': bld,
        'room_1': room_1,
        'room_2': room_2,
        'device_1': device_1,
        'alert_1': alert_1,
        'alert_2': alert_2,
    }


@pytest.mark.django_db
class TestAlertManagementAndAnomalyDetection:

    def test_list_and_filter_alerts(self, api_client, staff_user, alert_setup):
        api_client.force_authenticate(user=staff_user)

        response = api_client.get('/api/v1/alerts/')
        assert response.status_code == 200
        assert len(response.data['results']) == 2

        # Filter by severity=CRITICAL
        crit_resp = api_client.get('/api/v1/alerts/?severity=CRITICAL')
        assert crit_resp.status_code == 200
        assert len(crit_resp.data['results']) == 1
        assert crit_resp.data['results'][0]['title'] == "Critical Power Surge"

        # Filter by room_number
        room_resp = api_client.get('/api/v1/alerts/?room_number=M-101')
        assert room_resp.status_code == 200
        assert len(room_resp.data['results']) == 1
        assert room_resp.data['results'][0]['room_number'] == 'M-101'

    def test_alert_detail(self, api_client, staff_user, alert_setup):
        api_client.force_authenticate(user=staff_user)
        alert_id = alert_setup['alert_1'].id

        response = api_client.get(f'/api/v1/alerts/{alert_id}/')
        assert response.status_code == 200
        assert response.data['detection_method'] == 'RULE_BASED'
        assert response.data['building_code'] == 'BLD-M'
        assert response.data['device_hardware_id'] == 'ESP32-M101-01'

    def test_acknowledge_alert(self, api_client, staff_user, alert_setup):
        api_client.force_authenticate(user=staff_user)
        alert = alert_setup['alert_1']
        assert alert.is_acknowledged is False

        response = api_client.patch(f'/api/v1/alerts/{alert.id}/acknowledge/')
        assert response.status_code == 200
        assert response.data['status'] == 'ACKNOWLEDGED'

        alert.refresh_from_db()
        assert alert.is_acknowledged is True
        assert alert.acknowledged_by == 'Faculty Member'
        assert alert.acknowledged_at is not None

    def test_resolve_alert(self, api_client, staff_user, alert_setup):
        api_client.force_authenticate(user=staff_user)
        alert = alert_setup['alert_1']
        assert alert.is_resolved is False

        response = api_client.patch(f'/api/v1/alerts/{alert.id}/resolve/')
        assert response.status_code == 200
        assert response.data['status'] == 'RESOLVED'

        alert.refresh_from_db()
        assert alert.is_resolved is True
        assert alert.resolved_by == 'Faculty Member'

    def test_alert_summary_endpoint(self, api_client, staff_user, alert_setup):
        api_client.force_authenticate(user=staff_user)

        response = api_client.get('/api/v1/alerts/summary/')
        assert response.status_code == 200
        data = response.data
        assert data['total_unresolved'] == 2
        assert data['critical_count'] == 1
        assert data['high_count'] == 1
        assert data['total_power_wastage_watts'] == 5050.0

    def test_rule_based_anomaly_detection_vacant_room_wastage(self, alert_setup):
        bld = alert_setup['building']
        floor = bld.floors.first()
        test_room = Room.objects.create(
            floor=floor,
            name='Test Vacant Lab',
            room_number='M-201',
            occupancy_state=OccupancyStateChoices.EMPTY
        )

        # Ingest reading of 750W in empty room
        EnergyReading.objects.create(room=test_room, active_power_watts=750.0)

        alert = AnomalyDetectionService.evaluate_room_energy_anomaly(test_room)
        assert alert is not None
        assert alert.category == AlertCategoryChoices.ENERGY_WASTE
        assert alert.detection_method == 'RULE_BASED'
        assert alert.power_wastage_estimate_watts == 750.0

        # Verify duplicate alert prevention within 2 hours
        duplicate_attempt = AnomalyDetectionService.evaluate_room_energy_anomaly(test_room)
        assert duplicate_attempt is None

    def test_rule_based_anomaly_detection_critical_power_spike(self, alert_setup):
        bld = alert_setup['building']
        floor = bld.floors.first()
        test_room = Room.objects.create(
            floor=floor,
            name='High Load Testing Cell',
            room_number='M-301',
            occupancy_state=OccupancyStateChoices.ACTIVE
        )
        EnergyReading.objects.create(room=test_room, active_power_watts=4800.0)

        alert = AnomalyDetectionService.evaluate_room_energy_anomaly(test_room)
        assert alert is not None
        assert alert.severity == AlertSeverityChoices.CRITICAL
        assert alert.category == AlertCategoryChoices.SAFETY_TRIGGER

    def test_anomaly_scan_api_endpoint(self, api_client, staff_user, alert_setup):
        api_client.force_authenticate(user=staff_user)

        response = api_client.post('/api/v1/alerts/scan/')
        assert response.status_code == 200
        assert response.data['status'] == 'SCAN_COMPLETED'
        assert response.data['method'] == 'RULE_BASED'

    def test_unauthenticated_access_denied(self, api_client, alert_setup):
        response = api_client.get('/api/v1/alerts/')
        assert response.status_code == 401
