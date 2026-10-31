from rest_framework import serializers
from apps.rooms.models import Building, Floor, Room, RoomTypeChoices, OccupancyStateChoices

class BuildingSerializer(serializers.ModelSerializer):
    floors_count = serializers.IntegerField(source='floors.count', read_only=True)
    rooms_count = serializers.SerializerMethodField()

    class Meta:
        model = Building
        fields = [
            'id',
            'name',
            'code',
            'description',
            'total_floors',
            'floors_count',
            'rooms_count',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_rooms_count(self, obj):
        return Room.objects.filter(floor__building=obj).count()


class FloorSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    building_code = serializers.CharField(source='building.code', read_only=True)
    rooms_count = serializers.IntegerField(source='rooms.count', read_only=True)

    class Meta:
        model = Floor
        fields = [
            'id',
            'building',
            'building_name',
            'building_code',
            'level',
            'name',
            'rooms_count',
        ]
        read_only_fields = ['id']


class RoomListSerializer(serializers.ModelSerializer):
    building_id = serializers.IntegerField(source='floor.building.id', read_only=True)
    building_name = serializers.CharField(source='floor.building.name', read_only=True)
    building_code = serializers.CharField(source='floor.building.code', read_only=True)
    floor_level = serializers.IntegerField(source='floor.level', read_only=True)
    floor_name = serializers.CharField(source='floor.name', read_only=True)
    devices_count = serializers.IntegerField(source='devices.count', read_only=True)
    sensors_count = serializers.IntegerField(source='sensors.count', read_only=True)

    class Meta:
        model = Room
        fields = [
            'id',
            'floor',
            'floor_level',
            'floor_name',
            'building_id',
            'building_name',
            'building_code',
            'name',
            'room_number',
            'room_type',
            'occupancy_state',
            'ml_confidence_score',
            'idle_timer_minutes',
            'is_active',
            'devices_count',
            'sensors_count',
            'last_state_change',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'last_state_change']


class RoomDetailSerializer(serializers.ModelSerializer):
    building_id = serializers.IntegerField(source='floor.building.id', read_only=True)
    building_name = serializers.CharField(source='floor.building.name', read_only=True)
    building_code = serializers.CharField(source='floor.building.code', read_only=True)
    floor_level = serializers.IntegerField(source='floor.level', read_only=True)
    floor_name = serializers.CharField(source='floor.name', read_only=True)
    devices = serializers.SerializerMethodField()
    sensors = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id',
            'floor',
            'floor_level',
            'floor_name',
            'building_id',
            'building_name',
            'building_code',
            'name',
            'room_number',
            'room_type',
            'occupancy_state',
            'ml_confidence_score',
            'idle_timer_minutes',
            'is_active',
            'devices',
            'sensors',
            'last_state_change',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'last_state_change']

    def get_devices(self, obj):
        return [
            {
                'id': device.id,
                'name': device.name,
                'hardware_id': device.hardware_id,
                'device_type': device.device_type,
                'status': device.status,
                'wifi_rssi': device.wifi_rssi,
                'uptime_hours': device.uptime_hours,
            }
            for device in obj.devices.all()
        ]

    def get_sensors(self, obj):
        return [
            {
                'id': sensor.id,
                'sensor_type': sensor.sensor_type,
                'sensor_model': sensor.sensor_model,
                'unit_of_measurement': sensor.unit_of_measurement,
                'is_active': sensor.is_active,
            }
            for sensor in obj.sensors.all()
        ]

