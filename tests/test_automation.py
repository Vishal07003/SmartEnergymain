from datetime import timedelta
from django.utils import timezone
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices
from apps.rooms.models import Building, Floor, Room, OccupancyStateChoices
from apps.devices.models import Device, RelayChannel, DeviceTypeChoices, DeviceStatusChoices
from apps.telemetry.models import DeviceHeartbeat, TelemetryReading
from apps.sensors.models import Sensor, SensorTypeChoices
from apps.energy.models import EnergyReading
from apps.automation.models import (
    AutomationRule,
    AutomationLog,
    DeviceCommand,
    ConditionTypeChoices,
    ActionTypeChoices,
    CommandStatusChoices,
)
from apps.automation.services import AutomationExecutionEngine

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='auto_admin',
        email='auto_admin@institution.edu',
        password='AdminPassword123!',
        is_staff=True
    )
    StaffProfile.objects.create(user=user, employee_id='ADM-AUT-01', role=RoleChoices.ADMIN)
    return user

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='auto_staff',
        email='auto_staff@institution.edu',
        password='StaffPassword123!'
    )
    StaffProfile.objects.create(user=user, employee_id='FAC-AUT-02', role=RoleChoices.STAFF)
    return user

@pytest.fixture
def automation_setup(db):
    bld = Building.objects.create(name='Computing Hub', code='BLD-CH')
    floor = Floor.objects.create(building=bld, level=1, name='1st Floor')
    room_1 = Room.objects.create(floor=floor, name='Robotics Lab', room_number='CH-101', occupancy_state=OccupancyStateChoices.EMPTY)
    room_2 = Room.objects.create(floor=floor, name='AI Workshop', room_number='CH-102', occupancy_state=OccupancyStateChoices.ACTIVE)
    room_inactive = Room.objects.create(floor=floor, name='Old Archive', room_number='CH-999', is_active=False)

    dev_1 = Device.objects.create(
        room=room_1,
        name='ESP32 Node 101',
        hardware_id='ESP32-CH101-01',
        device_type=DeviceTypeChoices.ESP32_NODE
    )
    ch1 = RelayChannel.objects.create(device=dev_1, channel_index=1, label='Bench Lighting', is_on=True, safety_locked=False)
    ch2 = RelayChannel.objects.create(device=dev_1, channel_index=2, label='Exhaust Fan', is_on=True, safety_locked=False)
    ch3_locked = RelayChannel.objects.create(device=dev_1, channel_index=3, label='Server Core', is_on=True, safety_locked=True)

    # Device 2 has offline status (no fresh heartbeat)
    dev_2 = Device.objects.create(
        room=room_2,
        name='ESP32 Node 102',
        hardware_id='ESP32-CH102-02',
        device_type=DeviceTypeChoices.ESP32_NODE
    )
    ch_dev2 = RelayChannel.objects.create(device=dev_2, channel_index=1, label='Projector', is_on=False, safety_locked=False)

    # Fresh heartbeat for Device 1
    DeviceHeartbeat.objects.create(device=dev_1, voltage=230.0, current=1.5, power_watts=345.0)

    # Rule 1: Vacancy auto switch off
    rule_vacancy = AutomationRule.objects.create(
        name="Auto-Off Vacant Room 101",
        room=room_1,
        device=dev_1,
        channel=ch1,
        condition_type=ConditionTypeChoices.VACANCY_TIMEOUT,
        threshold_value=10.0,  # 10 minutes
        action_type=ActionTypeChoices.TURN_OFF_RELAY
    )

    return {
        'room_1': room_1,
        'room_2': room_2,
        'room_inactive': room_inactive,
        'dev_1': dev_1,
        'dev_2': dev_2,
        'ch1': ch1,
        'ch2': ch2,
        'ch3_locked': ch3_locked,
        'ch_dev2': ch_dev2,
        'rule_vacancy': rule_vacancy,
    }


@pytest.mark.django_db
class TestAutomationAndDeviceControl:

    def test_admin_can_create_automation_rule(self, api_client, admin_user, automation_setup):
        api_client.force_authenticate(user=admin_user)
        payload = {
            'name': 'Overheat Protection Fan',
            'room': automation_setup['room_1'].id,
            'device': automation_setup['dev_1'].id,
            'channel': automation_setup['ch2'].id,
            'condition_type': ConditionTypeChoices.HIGH_TEMPERATURE,
            'threshold_value': 35.0,
            'action_type': ActionTypeChoices.TURN_ON_RELAY
        }
        resp = api_client.post('/api/v1/automation/rules/', payload, format='json')
        assert resp.status_code == 201
        assert resp.data['name'] == 'Overheat Protection Fan'
        assert AutomationRule.objects.filter(name='Overheat Protection Fan').exists()

    def test_rule_creation_rejected_for_safety_locked_channel(self, api_client, admin_user, automation_setup):
        api_client.force_authenticate(user=admin_user)
        payload = {
            'name': 'Unsafe Auto Rule',
            'room': automation_setup['room_1'].id,
            'device': automation_setup['dev_1'].id,
            'channel': automation_setup['ch3_locked'].id,
            'condition_type': ConditionTypeChoices.VACANCY_TIMEOUT,
            'threshold_value': 5.0,
            'action_type': ActionTypeChoices.TURN_OFF_RELAY
        }
        resp = api_client.post('/api/v1/automation/rules/', payload, format='json')
        assert resp.status_code == 400
        assert 'safety-locked' in str(resp.data)

    def test_staff_cannot_create_automation_rule(self, api_client, staff_user, automation_setup):
        api_client.force_authenticate(user=staff_user)
        payload = {
            'name': 'Unauthorized Rule',
            'room': automation_setup['room_1'].id,
            'device': automation_setup['dev_1'].id,
            'condition_type': ConditionTypeChoices.VACANCY_TIMEOUT,
            'threshold_value': 10.0,
            'action_type': ActionTypeChoices.TURN_OFF_RELAY
        }
        resp = api_client.post('/api/v1/automation/rules/', payload, format='json')
        assert resp.status_code == 403

    def test_empty_room_automation_evaluation(self, automation_setup):
        rule = automation_setup['rule_vacancy']
        room = automation_setup['room_1']
        ch1 = automation_setup['ch1']
        assert ch1.is_on

        # Set room empty state change 15 minutes ago
        room.last_state_change = timezone.now() - timedelta(minutes=15)
        room.save()

        log = AutomationExecutionEngine.evaluate_rule(rule, force=True)
        assert log is not None
        assert log.execution_result == 'COMMAND_QUEUED'
        assert log.command is not None
        assert log.command.target_state is False

        # Verify physical honesty: RelayChannel.is_on remains unchanged before hardware ACK
        ch1.refresh_from_db()
        assert ch1.is_on

    def test_automation_skips_when_device_offline(self, automation_setup):
        dev_2 = automation_setup['dev_2']
        room_2 = automation_setup['room_2']
        ch = automation_setup['ch_dev2']

        rule_offline = AutomationRule.objects.create(
            name="Offline Device Rule",
            room=room_2,
            device=dev_2,
            channel=ch,
            condition_type=ConditionTypeChoices.OCCUPANCY_ACTIVE,
            action_type=ActionTypeChoices.TURN_ON_RELAY
        )

        log = AutomationExecutionEngine.evaluate_rule(rule_offline, force=True)
        assert log is not None
        assert log.execution_result == 'SKIPPED_DEVICE_OFFLINE'
        assert DeviceCommand.objects.filter(rule=rule_offline).count() == 0

    def test_manual_device_control_and_honesty(self, api_client, staff_user, automation_setup):
        api_client.force_authenticate(user=staff_user)
        dev_1 = automation_setup['dev_1']
        ch1 = automation_setup['ch1']
        assert ch1.is_on

        payload = {
            'device_id': dev_1.id,
            'channel_index': 1,
            'target_state': False,
            'reason': 'Manual staff shutdown'
        }
        resp = api_client.post('/api/v1/automation/manual-control/', payload, format='json')
        assert resp.status_code == 202
        cmd_id = resp.data['command_id']
        assert resp.data['status'] == 'QUEUED_FOR_DEVICE'
        assert resp.data['hardware_ack_received'] is False

        # Channel state is NOT changed prematurely
        ch1.refresh_from_db()
        assert ch1.is_on

        # Send hardware ACK packet
        ack_resp = api_client.post('/api/v1/automation/commands/acknowledge/', {
            'command_id': cmd_id,
            'reported_state': False,
            'hardware_notes': 'Physical contactor toggled successfully.'
        }, format='json')
        assert ack_resp.status_code == 200
        assert ack_resp.data['status'] == 'ACKNOWLEDGED'

        # Now and only now state updates
        ch1.refresh_from_db()
        assert not ch1.is_on

    def test_manual_control_rejection_for_safety_locked_channel(self, api_client, staff_user, automation_setup):
        api_client.force_authenticate(user=staff_user)
        dev_1 = automation_setup['dev_1']

        payload = {
            'device_id': dev_1.id,
            'channel_index': 3,  # safety_locked
            'target_state': False
        }
        resp = api_client.post('/api/v1/automation/manual-control/', payload, format='json')
        assert resp.status_code == 400
        assert 'safety-locked' in str(resp.data)

    def test_automation_logs_and_filtering(self, api_client, staff_user, automation_setup):
        api_client.force_authenticate(user=staff_user)

        AutomationLog.objects.create(
            device=automation_setup['dev_1'],
            room=automation_setup['room_1'],
            action_taken="TURN_OFF_RELAY",
            trigger_condition="VACANCY_TIMEOUT",
            execution_result="COMMAND_QUEUED"
        )

        resp = api_client.get('/api/v1/automation/logs/')
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 1

    def test_automation_evaluate_cycle_endpoint(self, api_client, staff_user, automation_setup):
        api_client.force_authenticate(user=staff_user)

        resp = api_client.post('/api/v1/automation/evaluate/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'CYCLE_COMPLETED'
        assert resp.data['rules_evaluated'] >= 1
