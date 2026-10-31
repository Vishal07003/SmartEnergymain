from datetime import timedelta
from typing import Optional, List, Dict, Any
from django.utils import timezone
from apps.automation.models import (
    AutomationRule,
    AutomationLog,
    DeviceCommand,
    ConditionTypeChoices,
    ActionTypeChoices,
    CommandStatusChoices,
    CommandSourceChoices,
)
from apps.rooms.models import Room, OccupancyStateChoices
from apps.devices.models import Device, RelayChannel
from apps.devices.serializers import compute_live_device_status
from apps.telemetry.models import TelemetryReading
from apps.energy.models import EnergyReading

class AutomationExecutionEngine:
    """
    Decoupled, verifiable automation execution service.
    Can be invoked on-demand via API or attached to periodic cron/Celery workers.
    """

    @classmethod
    def evaluate_rule(cls, rule: AutomationRule, force: bool = False) -> Optional[AutomationLog]:
        """
        Evaluates a single automation rule against current room state and telemetry.
        """
        if not rule.is_enabled:
            return None

        room = rule.room
        device = rule.device
        channel = rule.channel

        # Safety Check 1: Respect physical safety lock
        if channel and channel.safety_locked:
            return AutomationLog.objects.create(
                rule=rule,
                device=device,
                room=room,
                action_taken=rule.action_type,
                trigger_condition=rule.condition_type,
                execution_result='SKIPPED_SAFETY_LOCK',
                details=f"Channel {channel.channel_index} ({channel.label}) is safety-locked. Automated control prevented.",
                failure_reason="Safety lock active."
            )

        # Safety Check 2: Device availability (Do not issue actions to offline/unknown devices)
        live_status = compute_live_device_status(device)
        if live_status in ['OFFLINE', 'UNKNOWN']:
            return AutomationLog.objects.create(
                rule=rule,
                device=device,
                room=room,
                action_taken=rule.action_type,
                trigger_condition=rule.condition_type,
                execution_result='SKIPPED_DEVICE_OFFLINE',
                details=f"Device {device.hardware_id} is {live_status}. Commands cannot be delivered safely.",
                failure_reason=f"Device is {live_status}."
            )

        # Condition Evaluation
        should_trigger = False
        condition_reason = ""

        # Condition A: Room remains EMPTY for configured threshold
        if rule.condition_type == ConditionTypeChoices.VACANCY_TIMEOUT:
            if room.occupancy_state == OccupancyStateChoices.EMPTY:
                # Check idle minutes or last_state_change duration
                time_empty_minutes = (timezone.now() - room.last_state_change).total_seconds() / 60.0
                if time_empty_minutes >= rule.threshold_value:
                    should_trigger = True
                    condition_reason = f"Room {room.room_number} vacant for {time_empty_minutes:.1f}m (Threshold: {rule.threshold_value}m)"

        # Condition B: Room becomes ACTIVE
        elif rule.condition_type == ConditionTypeChoices.OCCUPANCY_ACTIVE:
            if room.occupancy_state == OccupancyStateChoices.ACTIVE:
                should_trigger = True
                condition_reason = f"Room {room.room_number} occupancy transitioned to ACTIVE"

        # Condition C: Energy power consumption exceeds threshold
        elif rule.condition_type == ConditionTypeChoices.ENERGY_THRESHOLD:
            latest_energy = EnergyReading.objects.filter(room=room).order_by('-timestamp').first()
            if latest_energy:
                reading_age = (timezone.now() - latest_energy.timestamp).total_seconds()
                if reading_age <= 300:  # Must be fresh within 5 minutes
                    if latest_energy.active_power_watts >= rule.threshold_value:
                        should_trigger = True
                        condition_reason = f"Active power {latest_energy.active_power_watts:.1f}W exceeded threshold {rule.threshold_value}W"

        # Condition D: High Temperature threshold
        elif rule.condition_type == ConditionTypeChoices.HIGH_TEMPERATURE:
            latest_temp = TelemetryReading.objects.filter(
                sensor__room=room,
                sensor__sensor_type='TEMPERATURE'
            ).order_by('-timestamp').first()
            if latest_temp:
                reading_age = (timezone.now() - latest_temp.timestamp).total_seconds()
                if reading_age <= 300:
                    if latest_temp.value >= rule.threshold_value:
                        should_trigger = True
                        condition_reason = f"Temperature {latest_temp.value:.1f}°C exceeded threshold {rule.threshold_value}°C"

        if not should_trigger and not force:
            return None

        # Prevent duplicate execution: check if triggered within past 15 minutes for unchanged state
        if not force and rule.last_triggered_at:
            if (timezone.now() - rule.last_triggered_at).total_seconds() < 900:
                return None

        # Execute configured action by queuing a validated DeviceCommand
        target_state = (rule.action_type == ActionTypeChoices.TURN_ON_RELAY)
        target_channel = channel or device.channels.first()

        if not target_channel:
            return AutomationLog.objects.create(
                rule=rule,
                device=device,
                room=room,
                action_taken=rule.action_type,
                trigger_condition=condition_reason or rule.condition_type,
                execution_result='FAILED_NO_CHANNEL',
                failure_reason="No relay channel found on target device."
            )

        cmd = DeviceCommand.objects.create(
            device=device,
            channel=target_channel,
            source=CommandSourceChoices.AUTOMATION,
            rule=rule,
            target_state=target_state,
            status=CommandStatusChoices.QUEUED,
            payload={
                'rule_name': rule.name,
                'condition': condition_reason or rule.condition_type,
                'action': rule.action_type
            }
        )

        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=['last_triggered_at'])

        log = AutomationLog.objects.create(
            rule=rule,
            device=device,
            room=room,
            command=cmd,
            action_taken=rule.action_type,
            trigger_condition=condition_reason or rule.condition_type,
            execution_result='COMMAND_QUEUED',
            details=f"Automation rule '{rule.name}' queued command {cmd.command_id} for channel {target_channel.channel_index}.",
            energy_saved_estimate_kwh=0.5 if not target_state else 0.0
        )
        return log

    @classmethod
    def evaluate_all_rules(cls) -> List[AutomationLog]:
        """
        Iterates over all active automation rules across campus.
        """
        logs = []
        rules = AutomationRule.objects.filter(is_enabled=True).select_related('room', 'device', 'channel')
        for rule in rules:
            result = cls.evaluate_rule(rule)
            if result:
                logs.append(result)
        return logs
