from rest_framework import serializers
from apps.automation.models import (
    AutomationRule,
    AutomationLog,
    DeviceCommand,
    ConditionTypeChoices,
    ActionTypeChoices,
    CommandStatusChoices,
)
from apps.rooms.models import Room
from apps.devices.models import Device, RelayChannel

class AutomationRuleSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True)
    channel_index = serializers.IntegerField(source='channel.channel_index', read_only=True, default=None)
    channel_label = serializers.CharField(source='channel.label', read_only=True, default=None)

    class Meta:
        model = AutomationRule
        fields = [
            'id',
            'name',
            'description',
            'room',
            'room_number',
            'building_code',
            'device',
            'device_hardware_id',
            'channel',
            'channel_index',
            'channel_label',
            'condition_type',
            'threshold_value',
            'action_type',
            'is_enabled',
            'last_triggered_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'last_triggered_at', 'created_at', 'updated_at']

    def validate(self, attrs):
        room = attrs.get('room') or getattr(self.instance, 'room', None)
        device = attrs.get('device') or getattr(self.instance, 'device', None)
        channel = attrs.get('channel') or getattr(self.instance, 'channel', None)

        if room and not room.is_active:
            raise serializers.ValidationError({'room': 'Cannot associate an automation rule with an inactive room.'})

        if device and room and device.room_id != room.id:
            raise serializers.ValidationError({
                'device': f"Device '{device.hardware_id}' belongs to Room '{device.room.room_number}', not Room '{room.room_number}'."
            })

        if channel and device and channel.device_id != device.id:
            raise serializers.ValidationError({
                'channel': f"Relay channel {channel.id} does not belong to device '{device.hardware_id}'."
            })

        if channel and channel.safety_locked:
            raise serializers.ValidationError({
                'channel': f"Relay channel {channel.channel_index} ({channel.label}) is safety-locked against automation."
            })

        return attrs


class DeviceCommandSerializer(serializers.ModelSerializer):
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True)
    channel_index = serializers.IntegerField(source='channel.channel_index', read_only=True)
    channel_label = serializers.CharField(source='channel.label', read_only=True)
    issued_by_username = serializers.CharField(source='issued_by.username', read_only=True, default=None)
    rule_name = serializers.CharField(source='rule.name', read_only=True, default=None)

    class Meta:
        model = DeviceCommand
        fields = [
            'id',
            'command_id',
            'device',
            'device_hardware_id',
            'channel',
            'channel_index',
            'channel_label',
            'source',
            'rule',
            'rule_name',
            'issued_by',
            'issued_by_username',
            'target_state',
            'status',
            'payload',
            'failure_reason',
            'hardware_ack_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'command_id', 'created_at', 'updated_at']


class ManualControlSerializer(serializers.Serializer):
    device_id = serializers.IntegerField(required=True)
    channel_index = serializers.IntegerField(required=True, min_value=1)
    target_state = serializers.BooleanField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        device_id = attrs['device_id']
        channel_index = attrs['channel_index']

        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            raise serializers.ValidationError({'device_id': f"Device with ID {device_id} does not exist."})

        try:
            channel = device.channels.get(channel_index=channel_index)
        except RelayChannel.DoesNotExist:
            raise serializers.ValidationError({'channel_index': f"Channel #{channel_index} does not exist on device '{device.hardware_id}'."})

        if not channel.is_controllable:
            raise serializers.ValidationError({'channel_index': f"Channel #{channel_index} is non-controllable."})

        if channel.safety_locked:
            raise serializers.ValidationError({'channel_index': f"Channel #{channel_index} is safety-locked. Manual override rejected."})

        attrs['device_instance'] = device
        attrs['channel_instance'] = channel
        return attrs


class CommandAcknowledgeSerializer(serializers.Serializer):
    command_id = serializers.CharField(required=True)
    reported_state = serializers.BooleanField(required=True)
    hardware_notes = serializers.CharField(required=False, allow_blank=True, default='')


class AutomationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True, default=None)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True, default=None)
    command_id = serializers.CharField(source='command.command_id', read_only=True, default=None)

    class Meta:
        model = AutomationLog
        fields = [
            'id',
            'rule',
            'rule_name',
            'device',
            'device_hardware_id',
            'room',
            'room_number',
            'command',
            'command_id',
            'action_taken',
            'trigger_condition',
            'execution_result',
            'details',
            'failure_reason',
            'energy_saved_estimate_kwh',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class AutomationEvaluateResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    rules_evaluated = serializers.IntegerField()
    commands_generated = serializers.IntegerField()
    logs_created = serializers.IntegerField()
