from django.db import models
from apps.rooms.models import Room
from apps.devices.models import Device

class ConditionTypeChoices(models.TextChoices):
    VACANCY_TIMEOUT = 'VACANCY_TIMEOUT', 'Vacancy Timeout'
    LUX_THRESHOLD = 'LUX_THRESHOLD', 'Lux Ambient Threshold'
    SCHEDULED_TIME = 'SCHEDULED_TIME', 'Scheduled Time'
    HIGH_TEMPERATURE = 'HIGH_TEMPERATURE', 'High Temperature'
    OVERCURRENT = 'OVERCURRENT', 'Overcurrent Protection'

class ActionTypeChoices(models.TextChoices):
    TURN_OFF_RELAY = 'TURN_OFF_RELAY', 'Turn Off Relay'
    DIM_LIGHTS = 'DIM_LIGHTS', 'Dim Lights'
    SEND_ALERT = 'SEND_ALERT', 'Send Alert'
    SWITCH_PROFILE = 'SWITCH_PROFILE', 'Switch Power Profile'

class AutomationRule(models.Model):
    name = models.CharField(max_length=128)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='automation_rules')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='automation_rules')
    condition_type = models.CharField(
        max_length=32,
        choices=ConditionTypeChoices.choices,
        default=ConditionTypeChoices.VACANCY_TIMEOUT
    )
    threshold_value = models.FloatField(default=15.0)  # e.g., 15 minutes vacancy or 350 Lux
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

class AutomationLog(models.Model):
    rule = models.ForeignKey(AutomationRule, on_delete=models.SET_NULL, null=True, related_name='logs')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='automation_logs')
    action_taken = models.CharField(max_length=128)
    details = models.TextField(blank=True)
    energy_saved_estimate_kwh = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'automation_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'Log: {self.action_taken} on {self.device.hardware_id} at {self.timestamp}'

