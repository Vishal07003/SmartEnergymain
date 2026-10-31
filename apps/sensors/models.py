from django.db import models
from apps.rooms.models import Room
from apps.devices.models import Device

class SensorTypeChoices(models.TextChoices):
    PIR_MOTION = 'PIR_MOTION', 'PIR Motion Sensor'
    TEMPERATURE = 'TEMPERATURE', 'Temperature Sensor'
    HUMIDITY = 'HUMIDITY', 'Humidity Sensor'
    AMBIENT_LIGHT = 'AMBIENT_LIGHT', 'Ambient Light (Lux) Sensor'
    SOUND_ACOUSTIC = 'SOUND_ACOUSTIC', 'Sound / Acoustic Sensor'
    CURRENT_POWER = 'CURRENT_POWER', 'Current / Power CT Clamp'

class Sensor(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='sensors')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='sensors')
    sensor_type = models.CharField(max_length=32, choices=SensorTypeChoices.choices, db_index=True)
    sensor_model = models.CharField(max_length=64, default='DHT22 / PIR-HC-SR501')
    unit_of_measurement = models.CharField(max_length=16, default='°C')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sensors'
        ordering = ['room', 'sensor_type']

    def __str__(self):
        return f'{self.room.room_number} - {self.sensor_type}'

