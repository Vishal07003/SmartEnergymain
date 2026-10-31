import django_filters
from apps.alerts.models import AIAlert, AlertSeverityChoices, AlertCategoryChoices

class AlertFilter(django_filters.FilterSet):
    severity = django_filters.ChoiceFilter(choices=AlertSeverityChoices.choices)
    category = django_filters.ChoiceFilter(choices=AlertCategoryChoices.choices)
    is_acknowledged = django_filters.BooleanFilter(field_name='is_acknowledged')
    is_resolved = django_filters.BooleanFilter(field_name='is_resolved')
    room = django_filters.NumberFilter(field_name='room__id')
    room_number = django_filters.CharFilter(field_name='room__room_number', lookup_expr='iexact')
    floor = django_filters.NumberFilter(field_name='room__floor__id')
    floor_level = django_filters.NumberFilter(field_name='room__floor__level')
    building = django_filters.NumberFilter(field_name='room__floor__building__id')
    building_code = django_filters.CharFilter(field_name='room__floor__building__code', lookup_expr='iexact')
    device = django_filters.NumberFilter(field_name='device__id')
    hardware_id = django_filters.CharFilter(field_name='device__hardware_id', lookup_expr='iexact')
    start_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = AIAlert
        fields = [
            'severity',
            'category',
            'is_acknowledged',
            'is_resolved',
            'room',
            'room_number',
            'floor',
            'floor_level',
            'building',
            'building_code',
            'device',
            'hardware_id',
            'start_time',
            'end_time',
        ]
