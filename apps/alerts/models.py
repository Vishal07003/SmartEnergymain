from django.db import models
from apps.rooms.models import Room
from apps.devices.models import Device

class AlertSeverityChoices(models.TextChoices):
    CRITICAL = 'CRITICAL', 'Critical'
    WARNING = 'WARNING', 'Warning'
    INFO = 'INFO', 'Informational'

class AlertCategoryChoices(models.TextChoices):
    ENERGY_WASTE = 'ENERGY_WASTE', 'Energy Waste'
    OCCUPANCY_ANOMALY = 'OCCUPANCY_ANOMALY', 'Occupancy Anomaly'
    DEVICE_OFFLINE = 'DEVICE_OFFLINE', 'Device Offline'
    HIGH_TEMPERATURE = 'HIGH_TEMPERATURE', 'High Temperature'
    SAFETY_TRIGGER = 'SAFETY_TRIGGER', 'Safety Trigger'

class AIAlert(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    severity = models.CharField(
        max_length=16,
        choices=AlertSeverityChoices.choices,
        default=AlertSeverityChoices.WARNING,
        db_index=True
    )
    category = models.CharField(
        max_length=32,
        choices=AlertCategoryChoices.choices,
        default=AlertCategoryChoices.ENERGY_WASTE,
        db_index=True
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='alerts')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='alerts')
    description = models.TextField()
    possible_reason = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    power_wastage_estimate_watts = models.FloatField(default=0.0)
    is_acknowledged = models.BooleanField(default=False, db_index=True)
    acknowledged_by = models.CharField(max_length=128, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'ai_alerts'
        indexes = [
            models.Index(fields=['room', '-timestamp']),
            models.Index(fields=['severity', 'is_acknowledged']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.severity}] {self.title} - {self.room.room_number}'

