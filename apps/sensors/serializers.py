from rest_framework import serializers
from apps.sensors.models import Sensor, SensorTypeChoices
from apps.devices.models import Device
from apps.rooms.models import Room
from apps.telemetry.models import TelemetryReading, DeviceHeartbeat

class SensorListSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True, default=None)
    latest_reading = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = [
            'id',
            'sensor_type',
            'sensor_model',
            'unit_of_measurement',
            'is_active',
            'room',
            'room_number',
            'room_name',
            'building_code',
            'device',
            'device_hardware_id',
            'latest_reading',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_latest_reading(self, obj):
        latest = obj.readings.order_by('-timestamp').first()
        if not latest:
            return None
        return {
            'value': latest.value,
            'timestamp': latest.timestamp,
        }


class SensorDetailSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    floor_level = serializers.IntegerField(source='room.floor.level', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    building_name = serializers.CharField(source='room.floor.building.name', read_only=True)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True, default=None)
    device_name = serializers.CharField(source='device.name', read_only=True, default=None)
    latest_reading = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = [
            'id',
            'sensor_type',
            'sensor_model',
            'unit_of_measurement',
            'is_active',
            'room',
            'room_number',
            'room_name',
            'floor_level',
            'building_code',
            'building_name',
            'device',
            'device_name',
            'device_hardware_id',
            'latest_reading',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_latest_reading(self, obj):
        latest = obj.readings.order_by('-timestamp').first()
        if not latest:
            return None
        return {
            'id': latest.id,
            'value': latest.value,
            'raw_payload': latest.raw_payload,
            'timestamp': latest.timestamp,
        }


class SensorCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = [
            'id',
            'room',
            'device',
            'sensor_type',
            'sensor_model',
            'unit_of_measurement',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        room = attrs.get('room')
        device = attrs.get('device')

        if room and not room.is_active:
            raise serializers.ValidationError({'room': 'Cannot assign a sensor to an inactive room.'})

        # If device is specified, ensure it belongs to the same room or validate compatibility
        if device and room and device.room_id != room.id:
            raise serializers.ValidationError({
                'device': f"Device '{device.hardware_id}' belongs to Room '{device.room.room_number}', not Room '{room.room_number}'."
            })
        return attrs


class TelemetryReadingSerializer(serializers.ModelSerializer):
    sensor_type = serializers.CharField(source='sensor.sensor_type', read_only=True)
    unit = serializers.CharField(source='sensor.unit_of_measurement', read_only=True)
    room_number = serializers.CharField(source='sensor.room.room_number', read_only=True)
    device_hardware_id = serializers.CharField(source='sensor.device.hardware_id', read_only=True, default=None)

    class Meta:
        model = TelemetryReading
        fields = [
            'id',
            'sensor',
            'sensor_type',
            'unit',
            'room_number',
            'device_hardware_id',
            'value',
            'raw_payload',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class TelemetryIngestSerializer(serializers.Serializer):
    device_hardware_id = serializers.CharField(required=True)
    sensor_id = serializers.IntegerField(required=True)
    value = serializers.FloatField(required=True)
    raw_payload = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        hw_id = attrs['device_hardware_id']
        sensor_id = attrs['sensor_id']

        try:
            device = Device.objects.get(hardware_id=hw_id)
        except Device.DoesNotExist:
            raise serializers.ValidationError({'device_hardware_id': f"Unrecognized hardware ID: '{hw_id}'."})

        try:
            sensor = Sensor.objects.select_related('device', 'room').get(id=sensor_id)
        except Sensor.DoesNotExist:
            raise serializers.ValidationError({'sensor_id': f"Sensor ID {sensor_id} does not exist."})

        if not sensor.is_active:
            raise serializers.ValidationError({'sensor_id': f"Sensor {sensor_id} is marked inactive."})

        # Validate that sensor is associated with this device
        if sensor.device_id != device.id:
            raise serializers.ValidationError({
                'sensor_id': f"Sensor {sensor_id} is not mapped to device '{hw_id}'."
            })

        attrs['device_instance'] = device
        attrs['sensor_instance'] = sensor
        return attrs


class HeartbeatIngestSerializer(serializers.Serializer):
    device_hardware_id = serializers.CharField(required=True)
    voltage = serializers.FloatField(required=False, default=230.0, min_value=0.0)
    current = serializers.FloatField(required=False, default=0.0, min_value=0.0)
    power_watts = serializers.FloatField(required=False, default=0.0, min_value=0.0)
    wifi_rssi = serializers.IntegerField(required=False, default=-60, min_value=-120, max_value=0)
    uptime_seconds = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate(self, attrs):
        hw_id = attrs['device_hardware_id']
        try:
            device = Device.objects.get(hardware_id=hw_id)
        except Device.DoesNotExist:
            raise serializers.ValidationError({'device_hardware_id': f"Device '{hw_id}' not found."})
        attrs['device_instance'] = device
        return attrs
