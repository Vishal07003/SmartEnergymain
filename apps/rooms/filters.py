import django_filters
from apps.rooms.models import Room, Floor, Building

class RoomFilter(django_filters.FilterSet):
    building = django_filters.NumberFilter(field_name='floor__building__id')
    building_code = django_filters.CharFilter(field_name='floor__building__code', lookup_expr='iexact')
    floor_level = django_filters.NumberFilter(field_name='floor__level')
    occupancy_state = django_filters.CharFilter(field_name='occupancy_state', lookup_expr='iexact')
    room_type = django_filters.CharFilter(field_name='room_type', lookup_expr='iexact')
    is_active = django_filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = Room
        fields = ['floor', 'building', 'building_code', 'floor_level', 'occupancy_state', 'room_type', 'is_active']


class FloorFilter(django_filters.FilterSet):
    building = django_filters.NumberFilter(field_name='building__id')
    building_code = django_filters.CharFilter(field_name='building__code', lookup_expr='iexact')
    level = django_filters.NumberFilter(field_name='level')

    class Meta:
        model = Floor
        fields = ['building', 'building_code', 'level']

