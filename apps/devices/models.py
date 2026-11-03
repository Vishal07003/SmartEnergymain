import secrets
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from apps.rooms.models import Room

class DeviceTypeChoices(models.TextChoices):
    ESP32_NODE = 'ESP32_NODE', 'ESP32 Node'
    RELAY_MODULE = 'RELAY_MODULE', 'Relay Module'
    SMART_POWER_SOCKET = 'SMART_POWER_SOCKET', 'Smart Power Socket'
    CURRENT_SENSOR = 'CURRENT_SENSOR', 'Current Sensor'
    LIGHTING_BANK = 'LIGHTING_BANK', 'Lighting Bank'
    HVAC_FAN_CONTROLLER = 'HVAC_FAN_CONTROLLER', 'HVAC / Fan Controller'

class DeviceStatusChoices(models.TextChoices):
    ONLINE = 'ONLINE', 'Online'
    OFFLINE = 'OFFLINE', 'Offline'
    DEGRADED = 'DEGRADED', 'Degraded'

class Device(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=128)
    hardware_id = models.CharField(max_length=64, unique=True, db_index=True)
    device_type = models.CharField(max_length=32, choices=DeviceTypeChoices.choices, default=DeviceTypeChoices.ESP32_NODE)
    status = models.CharField(max_length=16, choices=DeviceStatusChoices.choices, default=DeviceStatusChoices.ONLINE, db_index=True)
    mac_address = models.CharField(max_length=32, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    firmware_version = models.CharField(max_length=32, default='v2.4.1')
    automation_enabled = models.BooleanField(default=True)
    auth_token_hash = models.CharField(max_length=128, blank=True, help_text="Hashed device authentication token/secret")
    uptime_hours = models.PositiveIntegerField(default=0)
    wifi_rssi = models.IntegerField(default=-60)
    last_communication_time = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'devices'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} [{self.hardware_id}] - {self.status}'

    def set_auth_token(self, raw_token: str) -> None:
        """Hash and securely store device authentication token."""
        self.auth_token_hash = make_password(raw_token)

    def verify_auth_token(self, raw_token: str) -> bool:
        """Verify provided raw device token against stored hash."""
        if not self.auth_token_hash or not raw_token:
            return False
        return check_password(raw_token, self.auth_token_hash)

    def rotate_auth_token(self) -> str:
        """Generate, hash, save, and return a new random 32-byte secret token."""
        raw_token = secrets.token_hex(32)
        self.set_auth_token(raw_token)
        self.save(update_fields=['auth_token_hash'])
        return raw_token

    def revoke_auth_token(self) -> None:
        """Revoke device authentication credentials."""
        self.auth_token_hash = ''
        self.save(update_fields=['auth_token_hash'])


class RelayChannel(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='channels')
    channel_index = models.PositiveSmallIntegerField(default=1)
    label = models.CharField(max_length=128)
    is_on = models.BooleanField(default=False)
    power_watts = models.FloatField(default=0.0)
    is_controllable = models.BooleanField(default=True)
    safety_locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_relay_channels'
        unique_together = ('device', 'channel_index')
        ordering = ['device', 'channel_index']

    def __str__(self):
        return f'{self.device.hardware_id} Ch#{self.channel_index} ({self.label}) - {"ON" if self.is_on else "OFF"}'

