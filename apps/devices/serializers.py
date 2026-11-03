from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from apps.devices.models import Device, RelayChannel, DeviceTypeChoices, DeviceStatusChoices
from apps.telemetry.models import DeviceHeartbeat
from apps.rooms.models import Room

# Configurable timeout for live device status determination (e.g., 3 minutes)
HEARTBEAT_OFFLINE_THRESHOLD_SECONDS = 180

def compute_live_device_status(device: Device) -> str:
    """
    Computes device status strictly based on real heartbeat timestamps.
    Returns:
    - 'UNKNOWN' if no heartbeat has ever been received.
    - 'ONLINE' if the latest heartbeat was within HEARTBEAT_OFFLINE_THRESHOLD_SECONDS.
    - 'OFFLINE' if the latest heartbeat exceeds the threshold.
    """
    latest_heartbeat = device.heartbeats.order_by('-timestamp').first()
    if not latest_heartbeat:
        return 'UNKNOWN'

    elapsed = (timezone.now() - latest_heartbeat.timestamp).total_seconds()
    if elapsed <= HEARTBEAT_OFFLINE_THRESHOLD_SECONDS:
        return 'ONLINE'
    return 'OFFLINE'


class RelayChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelayChannel
        fields = [
            'id',
            'channel_index',
            'label',
            'is_on',
            'power_watts',
            'is_controllable',
            'safety_locked',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


class DeviceHeartbeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceHeartbeat
        fields = [
            'id',
            'voltage',
            'current',
            'power_watts',
            'wifi_rssi',
            'uptime_seconds',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class DeviceListSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    floor_level = serializers.IntegerField(source='room.floor.level', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    building_name = serializers.CharField(source='room.floor.building.name', read_only=True)
    channels_count = serializers.IntegerField(source='channels.count', read_only=True)
    calculated_status = serializers.SerializerMethodField()
    last_heartbeat_timestamp = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'id',
            'name',
            'hardware_id',
            'device_type',
            'status',
            'calculated_status',
            'mac_address',
            'ip_address',
            'firmware_version',
            'automation_enabled',
            'uptime_hours',
            'wifi_rssi',
            'room',
            'room_number',
            'room_name',
            'floor_level',
            'building_code',
            'building_name',
            'channels_count',
            'last_heartbeat_timestamp',
            'last_communication_time',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'last_communication_time']

    def get_calculated_status(self, obj):
        return compute_live_device_status(obj)

    def get_last_heartbeat_timestamp(self, obj):
        latest = obj.heartbeats.order_by('-timestamp').first()
        return latest.timestamp if latest else None


class DeviceDetailSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    floor_level = serializers.IntegerField(source='room.floor.level', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    building_name = serializers.CharField(source='room.floor.building.name', read_only=True)
    channels = RelayChannelSerializer(many=True, read_only=True)
    latest_heartbeat = serializers.SerializerMethodField()
    calculated_status = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'id',
            'name',
            'hardware_id',
            'device_type',
            'status',
            'calculated_status',
            'mac_address',
            'ip_address',
            'firmware_version',
            'automation_enabled',
            'uptime_hours',
            'wifi_rssi',
            'room',
            'room_number',
            'room_name',
            'floor_level',
            'building_code',
            'building_name',
            'channels',
            'latest_heartbeat',
            'last_communication_time',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'last_communication_time']

    def get_calculated_status(self, obj):
        return compute_live_device_status(obj)

    def get_latest_heartbeat(self, obj):
        latest = obj.heartbeats.order_by('-timestamp').first()
        if not latest:
            return None
        return DeviceHeartbeatSerializer(latest).data


class DeviceCreateSerializer(serializers.ModelSerializer):
    channels = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
        help_text="Optional list of relay channel definitions, e.g. [{'channel_index': 1, 'label': 'Ceiling Lights'}]"
    )

    class Meta:
        model = Device
        fields = [
            'id',
            'name',
            'hardware_id',
            'device_type',
            'room',
            'mac_address',
            'ip_address',
            'firmware_version',
            'automation_enabled',
            'channels',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_hardware_id(self, value):
        if Device.objects.filter(hardware_id__iexact=value).exists():
            raise serializers.ValidationError(f"Device with Hardware ID '{value}' is already registered.")
        return value

    def create(self, validated_data):
        channels_data = validated_data.pop('channels', [])
        device = Device.objects.create(**validated_data)
        for ch in channels_data:
            RelayChannel.objects.create(
                device=device,
                channel_index=ch.get('channel_index', 1),
                label=ch.get('label', f"Channel {ch.get('channel_index', 1)}"),
                is_on=ch.get('is_on', False),
                is_controllable=ch.get('is_controllable', True),
                safety_locked=ch.get('safety_locked', False),
            )
        return device


class AssignRoomSerializer(serializers.Serializer):
    room_id = serializers.IntegerField(required=True)

    def validate_room_id(self, value):
        try:
            room = Room.objects.get(id=value)
        except Room.DoesNotExist:
            raise serializers.ValidationError(f"Room with ID {value} does not exist.")
        if not room.is_active:
            raise serializers.ValidationError("Cannot assign device to an inactive room.")
        return value


class DeviceCommandSerializer(serializers.Serializer):
    channel_index = serializers.IntegerField(required=True, min_value=1)
    target_state = serializers.BooleanField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        device = self.context.get('device')
        channel_index = attrs['channel_index']
        try:
            channel = device.channels.get(channel_index=channel_index)
        except RelayChannel.DoesNotExist:
            raise serializers.ValidationError({'channel_index': f"Channel #{channel_index} does not exist on device {device.hardware_id}."})

        if not channel.is_controllable:
            raise serializers.ValidationError({'channel_index': f"Channel #{channel_index} is flagged as non-controllable."})

        if channel.safety_locked:
            raise serializers.ValidationError({'channel_index': f"Channel #{channel_index} is safety-locked. Command rejected for physical safety."})

        attrs['channel_instance'] = channel
        return attrs


class DeviceRotateTokenResponseSerializer(serializers.Serializer):
    hardware_id = serializers.CharField()
    auth_token = serializers.CharField(help_text="One-time plaintext secret token for device MQTT/HTTP authentication.")
    message = serializers.CharField()

