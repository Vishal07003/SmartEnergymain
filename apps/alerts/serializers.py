from rest_framework import serializers
from apps.alerts.models import AIAlert, AlertSeverityChoices, AlertCategoryChoices
from apps.rooms.models import Room
from apps.devices.models import Device

class AIAlertListSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True, default=None)

    class Meta:
        model = AIAlert
        fields = [
            'id',
            'title',
            'severity',
            'category',
            'room',
            'room_number',
            'room_name',
            'building_code',
            'device',
            'device_hardware_id',
            'description',
            'power_wastage_estimate_watts',
            'detection_method',
            'is_acknowledged',
            'acknowledged_by',
            'acknowledged_at',
            'is_resolved',
            'resolved_by',
            'resolved_at',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class AIAlertDetailSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    floor_level = serializers.IntegerField(source='room.floor.level', read_only=True)
    building_name = serializers.CharField(source='room.floor.building.name', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True, default=None)
    device_name = serializers.CharField(source='device.name', read_only=True, default=None)

    class Meta:
        model = AIAlert
        fields = [
            'id',
            'title',
            'severity',
            'category',
            'room',
            'room_number',
            'room_name',
            'floor_level',
            'building_code',
            'building_name',
            'device',
            'device_name',
            'device_hardware_id',
            'description',
            'possible_reason',
            'recommended_action',
            'power_wastage_estimate_watts',
            'detection_method',
            'is_acknowledged',
            'acknowledged_by',
            'acknowledged_at',
            'is_resolved',
            'resolved_by',
            'resolved_at',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class AlertActionResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    alert_id = serializers.IntegerField()
    action = serializers.CharField()
    actor = serializers.CharField()
    timestamp = serializers.CharField()


class AlertSummarySerializer(serializers.Serializer):
    total_unresolved = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    high_count = serializers.IntegerField()
    medium_count = serializers.IntegerField()
    low_count = serializers.IntegerField()
    total_power_wastage_watts = serializers.FloatField()
    category_breakdown = serializers.DictField()

class AnomalyScanResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    rooms_scanned = serializers.IntegerField()
    new_alerts_created = serializers.IntegerField()
    alert_ids = serializers.ListField(child=serializers.IntegerField())
    method = serializers.CharField()
