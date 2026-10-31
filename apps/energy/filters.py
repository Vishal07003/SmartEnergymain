import django_filters
from apps.energy.models import EnergyReading, DailyEnergyAggregation

class EnergyReadingFilter(django_filters.FilterSet):
    room = django_filters.NumberFilter(field_name='room__id')
    room_number = django_filters.CharFilter(field_name='room__room_number', lookup_expr='iexact')
    building = django_filters.NumberFilter(field_name='room__floor__building__id')
    building_code = django_filters.CharFilter(field_name='room__floor__building__code', lookup_expr='iexact')
    device = django_filters.NumberFilter(field_name='device__id')
    hardware_id = django_filters.CharFilter(field_name='device__hardware_id', lookup_expr='iexact')
    start_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = EnergyReading
        fields = [
            'room',
            'room_number',
            'building',
            'building_code',
            'device',
            'hardware_id',
            'start_time',
            'end_time',
        ]


class DailyEnergyAggregationFilter(django_filters.FilterSet):
    room = django_filters.NumberFilter(field_name='room__id')
    room_number = django_filters.CharFilter(field_name='room__room_number', lookup_expr='iexact')
    building = django_filters.NumberFilter(field_name='room__floor__building__id')
    building_code = django_filters.CharFilter(field_name='room__floor__building__code', lookup_expr='iexact')
    start_date = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = DailyEnergyAggregation
        fields = [
            'room',
            'room_number',
            'building',
            'building_code',
            'start_date',
            'end_date',
        ]

