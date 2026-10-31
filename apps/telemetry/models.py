from django.db import models
from apps.sensors.models import Sensor
from apps.devices.models import Device

class TelemetryReading(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    value = models.FloatField()
    raw_payload = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'telemetry_readings'
        indexes = [
            models.Index(fields=['sensor', '-timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.sensor.sensor_type}: {self.value} at {self.timestamp}'

class DeviceHeartbeat(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='heartbeats')
    voltage = models.FloatField(default=230.0)
    current = models.FloatField(default=0.0)
    power_watts = models.FloatField(default=0.0)
    wifi_rssi = models.IntegerField(default=-60)
    uptime_seconds = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'device_heartbeats'
        indexes = [
            models.Index(fields=['device', '-timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.device.hardware_id} Heartbeat at {self.timestamp}'

