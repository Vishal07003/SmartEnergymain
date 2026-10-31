from django.db import models
from apps.rooms.models import Room
from apps.devices.models import Device

class EnergyReading(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='energy_readings')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='energy_readings')
    voltage_volts = models.FloatField(default=230.0)
    current_amps = models.FloatField(default=0.0)
    active_power_watts = models.FloatField(default=0.0, db_index=True)
    power_factor = models.FloatField(default=0.95)
    frequency_hz = models.FloatField(default=50.0)
    energy_kwh = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'energy_readings'
        indexes = [
            models.Index(fields=['room', '-timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.room.room_number}: {self.active_power_watts}W at {self.timestamp}'

class DailyEnergyAggregation(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='daily_aggregations')
    date = models.DateField(db_index=True)
    total_kwh = models.FloatField(default=0.0)
    peak_power_watts = models.FloatField(default=0.0)
    wasted_kwh_estimate = models.FloatField(default=0.0)
    saved_kwh_estimate = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daily_energy_aggregations'
        unique_together = ('room', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.room.room_number} - {self.date}: {self.total_kwh} kWh'

