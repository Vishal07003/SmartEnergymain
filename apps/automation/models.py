import uuid
from django.db import models
from django.contrib.auth.models import User
from apps.rooms.models import Room
from apps.devices.models import Device, RelayChannel

class ConditionTypeChoices(models.TextChoices):
    VACANCY_TIMEOUT = 'VACANCY_TIMEOUT', 'Vacancy Timeout'
    OCCUPANCY_ACTIVE = 'OCCUPANCY_ACTIVE', 'Occupancy Active'
    LUX_THRESHOLD = 'LUX_THRESHOLD', 'Lux Ambient Threshold'
    SCHEDULED_TIME = 'SCHEDULED_TIME', 'Scheduled Time'
    HIGH_TEMPERATURE = 'HIGH_TEMPERATURE', 'High Temperature'
    OVERCURRENT = 'OVERCURRENT', 'Overcurrent Protection'
    ENERGY_THRESHOLD = 'ENERGY_THRESHOLD', 'Energy Power Threshold'
    DEVICE_OFFLINE = 'DEVICE_OFFLINE', 'Device Offline'

class ActionTypeChoices(models.TextChoices):
    TURN_OFF_RELAY = 'TURN_OFF_RELAY', 'Turn Off Relay'
    TURN_ON_RELAY = 'TURN_ON_RELAY', 'Turn On Relay'
    DIM_LIGHTS = 'DIM_LIGHTS', 'Dim Lights'
    SEND_ALERT = 'SEND_ALERT', 'Send Alert'
    SWITCH_PROFILE = 'SWITCH_PROFILE', 'Switch Power Profile'

class CommandStatusChoices(models.TextChoices):
    QUEUED = 'QUEUED', 'Queued'
    SENT = 'SENT', 'Sent'
    ACKNOWLEDGED = 'ACKNOWLEDGED', 'Acknowledged'
    FAILED = 'FAILED', 'Failed'
    EXPIRED = 'EXPIRED', 'Expired'

class CommandSourceChoices(models.TextChoices):
    MANUAL = 'MANUAL', 'Manual User Control'
    AUTOMATION = 'AUTOMATION', 'Automation Engine'

class AutomationRule(models.Model):
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='automation_rules')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='automation_rules')
    channel = models.ForeignKey(RelayChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name='automation_rules')
    condition_type = models.CharField(
        max_length=32,
        choices=ConditionTypeChoices.choices,
        default=ConditionTypeChoices.VACANCY_TIMEOUT
    )
    threshold_value = models.FloatField(default=15.0)  # e.g., 15 minutes vacancy, 350 Lux, 36.0 °C, or 2500 Watts
    action_type = models.CharField(
        max_length=32,
        choices=ActionTypeChoices.choices,
        default=ActionTypeChoices.TURN_OFF_RELAY
    )
    is_enabled = models.BooleanField(default=True, db_index=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automation_rules'
        ordering = ['room', 'name']

    def __str__(self):
        return f'{self.name} ({self.room.room_number}) - {"Enabled" if self.is_enabled else "Disabled"}'


class DeviceCommand(models.Model):
    command_id = models.CharField(max_length=64, unique=True, db_index=True, default=uuid.uuid4)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='dispatched_commands')
    channel = models.ForeignKey(RelayChannel, on_delete=models.CASCADE, related_name='dispatched_commands')
    source = models.CharField(max_length=16, choices=CommandSourceChoices.choices, default=CommandSourceChoices.MANUAL)
    rule = models.ForeignKey(AutomationRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_commands')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatched_commands')
    target_state = models.BooleanField()  # True for ON, False for OFF
    status = models.CharField(
        max_length=16,
        choices=CommandStatusChoices.choices,
        default=CommandStatusChoices.QUEUED,
        db_index=True
    )
    payload = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)
    hardware_ack_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_commands'
        ordering = ['-created_at']

    def __str__(self):
        return f'Command [{self.command_id}] {self.device.hardware_id} Ch#{self.channel.channel_index} -> {"ON" if self.target_state else "OFF"} ({self.status})'


class AutomationLog(models.Model):
    rule = models.ForeignKey(AutomationRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='automation_logs')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True, related_name='automation_logs')
    command = models.ForeignKey(DeviceCommand, on_delete=models.SET_NULL, null=True, blank=True, related_name='automation_logs')
    action_taken = models.CharField(max_length=128)
    trigger_condition = models.CharField(max_length=128, blank=True)
    execution_result = models.CharField(max_length=32, default='SUCCESS')
    details = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    energy_saved_estimate_kwh = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'automation_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'Log: {self.action_taken} on {self.device.hardware_id} at {self.timestamp}'
