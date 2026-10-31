from rest_framework import serializers
from apps.energy.models import EnergyReading, DailyEnergyAggregation
from apps.rooms.models import Room
from apps.devices.models import Device

class EnergyReadingSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)
    device_hardware_id = serializers.CharField(source='device.hardware_id', read_only=True, default=None)

    class Meta:
        model = EnergyReading
        fields = [
            'id',
            'room',
            'room_number',
            'building_code',
            'device',
            'device_hardware_id',
            'voltage_volts',
            'current_amps',
            'active_power_watts',
            'power_factor',
            'frequency_hz',
            'energy_kwh',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class EnergyReadingIngestSerializer(serializers.Serializer):
    room_id = serializers.IntegerField(required=True)
    device_hardware_id = serializers.CharField(required=False, allow_null=True, default=None)
    voltage_volts = serializers.FloatField(required=False, default=230.0, min_value=0.0)
    current_amps = serializers.FloatField(required=True, min_value=0.0)
    active_power_watts = serializers.FloatField(required=True, min_value=0.0)
    power_factor = serializers.FloatField(required=False, default=0.95, min_value=0.0, max_value=1.0)
    frequency_hz = serializers.FloatField(required=False, default=50.0, min_value=0.0)
    energy_kwh = serializers.FloatField(required=False, default=0.0, min_value=0.0)

    def validate(self, attrs):
        room_id = attrs['room_id']
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            raise serializers.ValidationError({'room_id': f"Room with ID {room_id} not found."})

        if not room.is_active:
            raise serializers.ValidationError({'room_id': "Cannot record energy for an inactive room."})

        attrs['room_instance'] = room

        hw_id = attrs.get('device_hardware_id')
        if hw_id:
            try:
                device = Device.objects.get(hardware_id=hw_id)
            except Device.DoesNotExist:
                raise serializers.ValidationError({'device_hardware_id': f"Device '{hw_id}' not found."})
            if device.room_id != room.id:
                raise serializers.ValidationError({
                    'device_hardware_id': f"Device '{hw_id}' is assigned to room {device.room.room_number}, not {room.room_number}."
                })
            attrs['device_instance'] = device
        else:
            attrs['device_instance'] = None

        return attrs


class DailyEnergyAggregationSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    building_code = serializers.CharField(source='room.floor.building.code', read_only=True)

    class Meta:
        model = DailyEnergyAggregation
        fields = [
            'id',
            'room',
            'room_number',
            'building_code',
            'date',
            'total_kwh',
            'peak_power_watts',
            'wasted_kwh_estimate',
            'saved_kwh_estimate',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CampusEnergySummarySerializer(serializers.Serializer):
    total_consumption_kwh = serializers.FloatField()
    average_power_watts = serializers.FloatField()
    peak_power_watts = serializers.FloatField()
    active_monitoring_rooms = serializers.IntegerField()
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    waste_estimate_notice = serializers.CharField()


class BuildingEnergyItemSerializer(serializers.Serializer):
    building_id = serializers.IntegerField()
    building_name = serializers.CharField()
    building_code = serializers.CharField()
    total_kwh = serializers.FloatField()
    peak_power_watts = serializers.FloatField()


class BuildingComparisonResponseSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    since_date = serializers.CharField()
    buildings = BuildingEnergyItemSerializer(many=True)
