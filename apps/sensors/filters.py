import django_filters
from apps.sensors.models import Sensor, SensorTypeChoices
from apps.telemetry.models import TelemetryReading

class SensorFilter(django_filters.FilterSet):
    sensor_type = django_filters.ChoiceFilter(choices=SensorTypeChoices.choices)
    room = django_filters.NumberFilter(field_name='room__id')
    room_number = django_filters.CharFilter(field_name='room__room_number', lookup_expr='iexact')
    building = django_filters.NumberFilter(field_name='room__floor__building__id')
    building_code = django_filters.CharFilter(field_name='room__floor__building__code', lookup_expr='iexact')
    device = django_filters.NumberFilter(field_name='device__id')
    hardware_id = django_filters.CharFilter(field_name='device__hardware_id', lookup_expr='iexact')
    is_active = django_filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = Sensor
        fields = [
            'sensor_type',
            'room',
            'room_number',
            'building',
            'building_code',
            'device',
            'hardware_id',
            'is_active',
        ]


class TelemetryReadingFilter(django_filters.FilterSet):
    sensor = django_filters.NumberFilter(field_name='sensor__id')
    sensor_type = django_filters.ChoiceFilter(field_name='sensor__sensor_type', choices=SensorTypeChoices.choices)
    device = django_filters.NumberFilter(field_name='sensor__device__id')
    hardware_id = django_filters.CharFilter(field_name='sensor__device__hardware_id', lookup_expr='iexact')
    room = django_filters.NumberFilter(field_name='sensor__room__id')
    room_number = django_filters.CharFilter(field_name='sensor__room__room_number', lookup_expr='iexact')
    start_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = TelemetryReading
        fields = [
            'sensor',
            'sensor_type',
            'device',
            'hardware_id',
            'room',
            'room_number',
            'start_time',
            'end_time',
        ]
