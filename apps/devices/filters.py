import django_filters
from apps.devices.models import Device, DeviceTypeChoices, DeviceStatusChoices

class DeviceFilter(django_filters.FilterSet):
    building = django_filters.NumberFilter(field_name='room__floor__building__id')
    building_code = django_filters.CharFilter(field_name='room__floor__building__code', lookup_expr='iexact')
    floor = django_filters.NumberFilter(field_name='room__floor__id')
    floor_level = django_filters.NumberFilter(field_name='room__floor__level')
    room = django_filters.NumberFilter(field_name='room__id')
    room_number = django_filters.CharFilter(field_name='room__room_number', lookup_expr='iexact')
    device_type = django_filters.ChoiceFilter(choices=DeviceTypeChoices.choices)
    status = django_filters.ChoiceFilter(choices=DeviceStatusChoices.choices)
    automation_enabled = django_filters.BooleanFilter(field_name='automation_enabled')

    class Meta:
        model = Device
        fields = [
            'building',
            'building_code',
            'floor',
            'floor_level',
            'room',
            'room_number',
            'device_type',
            'status',
            'automation_enabled',
        ]
