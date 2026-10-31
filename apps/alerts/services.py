from datetime import timedelta
from typing import List, Optional, Dict, Any
from django.utils import timezone
from apps.alerts.models import AIAlert, AlertSeverityChoices, AlertCategoryChoices
from apps.rooms.models import Room, OccupancyStateChoices
from apps.devices.models import Device
from apps.telemetry.models import DeviceHeartbeat, TelemetryReading
from apps.energy.models import EnergyReading

# Configurable detection thresholds
HIGH_POWER_CRITICAL_THRESHOLD_WATTS = 4000.0   # 4 kW in single room
EMPTY_ROOM_WASTAGE_THRESHOLD_WATTS = 300.0     # Power consumed while room is confirmed EMPTY
TEMPERATURE_HIGH_THRESHOLD_CELSIUS = 36.0      # Overheating threshold
HEARTBEAT_TIMEOUT_SECONDS = 300                # 5 minutes offline threshold

class AnomalyDetectionService:
    """
    Transparent, verifiable rule-based anomaly detection engine.
    Designed with hooks ready for trained ML model integration (e.g., Random Forest/XGBoost).
    """

    @classmethod
    def evaluate_room_energy_anomaly(cls, room: Room) -> Optional[AIAlert]:
        """
        Detects energy consumption anomalies:
        1. High power draw in an empty room (Occupancy mismatch).
        2. Dangerous overconsumption beyond institutional rating.
        """
        latest_energy = EnergyReading.objects.filter(room=room).order_by('-timestamp').first()
        if not latest_energy:
            return None

        # Rule 1: High wattage while room is confirmed EMPTY
        if room.occupancy_state == OccupancyStateChoices.EMPTY and latest_energy.active_power_watts >= EMPTY_ROOM_WASTAGE_THRESHOLD_WATTS:
            # Check for existing unresolved alert to prevent duplicates (within past 2 hours)
            two_hours_ago = timezone.now() - timedelta(hours=2)
            existing = AIAlert.objects.filter(
                room=room,
                category=AlertCategoryChoices.ENERGY_WASTE,
                is_resolved=False,
                timestamp__gte=two_hours_ago
            ).first()

            if not existing:
                severity = AlertSeverityChoices.HIGH if latest_energy.active_power_watts >= 1500.0 else AlertSeverityChoices.MEDIUM
                alert = AIAlert.objects.create(
                    title=f"Wastage in Empty Room {room.room_number}",
                    severity=severity,
                    category=AlertCategoryChoices.ENERGY_WASTE,
                    room=room,
                    device=latest_energy.device,
                    description=f"Active power draw of {latest_energy.active_power_watts:.1f}W detected while room is empty.",
                    possible_reason="Appraisal/HVAC or bench lighting left running after vacancy.",
                    recommended_action="Execute automated shutdown or check relay channels.",
                    power_wastage_estimate_watts=latest_energy.active_power_watts,
                    detection_method="RULE_BASED"
                )
                return alert

        # Rule 2: Critical Overcurrent / Super-high power draw
        if latest_energy.active_power_watts >= HIGH_POWER_CRITICAL_THRESHOLD_WATTS:
            four_hours_ago = timezone.now() - timedelta(hours=4)
            existing = AIAlert.objects.filter(
                room=room,
                severity=AlertSeverityChoices.CRITICAL,
                category=AlertCategoryChoices.SAFETY_TRIGGER,
                is_resolved=False,
                timestamp__gte=four_hours_ago
            ).first()

            if not existing:
                alert = AIAlert.objects.create(
                    title=f"Critical Power Surge in Room {room.room_number}",
                    severity=AlertSeverityChoices.CRITICAL,
                    category=AlertCategoryChoices.SAFETY_TRIGGER,
                    room=room,
                    device=latest_energy.device,
                    description=f"Measured active power reached {latest_energy.active_power_watts:.1f}W (Limit: {HIGH_POWER_CRITICAL_THRESHOLD_WATTS}W).",
                    possible_reason="Multiple heavy appliances operating simultaneously or short-circuit spike.",
                    recommended_action="Inspect sub-panel circuit breaker immediately.",
                    power_wastage_estimate_watts=latest_energy.active_power_watts,
                    detection_method="RULE_BASED"
                )
                return alert

        return None

    @classmethod
    def evaluate_device_offline_anomaly(cls, device: Device) -> Optional[AIAlert]:
        """
        Detects missing heartbeats from registered nodes.
        """
        latest_hb = device.heartbeats.order_by('-timestamp').first()
        now = timezone.now()

        # If device has never phoned home, or last heartbeat was > 5 minutes ago
        is_missing = False
        if not latest_hb:
            # Only flag if device was registered more than 10 minutes ago
            created_at = getattr(device, 'created_at', None)
            if created_at and (now - created_at).total_seconds() > 600:
                is_missing = True
        else:
            hb_timestamp = getattr(latest_hb, 'timestamp', None)
            if hb_timestamp and (now - hb_timestamp).total_seconds() > HEARTBEAT_TIMEOUT_SECONDS:
                is_missing = True

        if is_missing:
            one_day_ago = now - timedelta(days=1)
            existing = AIAlert.objects.filter(
                device=device,
                category=AlertCategoryChoices.DEVICE_OFFLINE,
                is_resolved=False,
                timestamp__gte=one_day_ago
            ).first()

            if not existing:
                alert = AIAlert.objects.create(
                    title=f"ESP32 Node Offline: {device.hardware_id}",
                    severity=AlertSeverityChoices.HIGH,
                    category=AlertCategoryChoices.DEVICE_OFFLINE,
                    room=device.room,
                    device=device,
                    description=f"Device {device.hardware_id} has not transmitted a heartbeat for > 5 minutes.",
                    possible_reason="Wi-Fi network failure, power supply interruption, or firmware crash.",
                    recommended_action="Check node 5V/3.3V DC power line and access point connection.",
                    detection_method="RULE_BASED"
                )
                return alert

        return None

    @classmethod
    def evaluate_temperature_sensor_anomaly(cls, room: Room) -> Optional[AIAlert]:
        """
        Detects dangerous high temperatures recorded by ambient sensors.
        """
        latest_temp = TelemetryReading.objects.filter(
            sensor__room=room,
            sensor__sensor_type='TEMPERATURE'
        ).order_by('-timestamp').first()

        if latest_temp and latest_temp.value >= TEMPERATURE_HIGH_THRESHOLD_CELSIUS:
            six_hours_ago = timezone.now() - timedelta(hours=6)
            existing = AIAlert.objects.filter(
                room=room,
                category=AlertCategoryChoices.HIGH_TEMPERATURE,
                is_resolved=False,
                timestamp__gte=six_hours_ago
            ).first()

            if not existing:
                alert = AIAlert.objects.create(
                    title=f"High Temperature in Room {room.room_number}",
                    severity=AlertSeverityChoices.CRITICAL if latest_temp.value >= 42.0 else AlertSeverityChoices.HIGH,
                    category=AlertCategoryChoices.HIGH_TEMPERATURE,
                    room=room,
                    device=latest_temp.sensor.device,
                    description=f"Ambient room temperature measured at {latest_temp.value:.1f}°C (Threshold: {TEMPERATURE_HIGH_THRESHOLD_CELSIUS}°C).",
                    possible_reason="HVAC failure, server heat exhaust concentration, or extreme weather.",
                    recommended_action="Inspect cooling units or emergency ventilation.",
                    detection_method="RULE_BASED"
                )
                return alert

        return None
