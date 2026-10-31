import django_filters
from apps.automation.models import AutomationRule, AutomationLog, DeviceCommand, ConditionTypeChoices, ActionTypeChoices, CommandStatusChoices

class AutomationRuleFilter(django_filters.FilterSet):
    room = django_filters.NumberFilter(field_name='room__id')
    room_number = django_filters.CharFilter(field_name='room__room_number', lookup_expr='iexact')
    device = django_filters.NumberFilter(field_name='device__id')
    hardware_id = django_filters.CharFilter(field_name='device__hardware_id', lookup_expr='iexact')
    condition_type = django_filters.ChoiceFilter(choices=ConditionTypeChoices.choices)
    action_type = django_filters.ChoiceFilter(choices=ActionTypeChoices.choices)
    is_enabled = django_filters.BooleanFilter(field_name='is_enabled')

    class Meta:
        model = AutomationRule
        fields = [
            'room',
            'room_number',
            'device',
            'hardware_id',
            'condition_type',
            'action_type',
            'is_enabled',
        ]


class DeviceCommandFilter(django_filters.FilterSet):
    device = django_filters.NumberFilter(field_name='device__id')
    hardware_id = django_filters.CharFilter(field_name='device__hardware_id', lookup_expr='iexact')
    status = django_filters.ChoiceFilter(choices=CommandStatusChoices.choices)
    source = django_filters.CharFilter(field_name='source', lookup_expr='iexact')
    rule = django_filters.NumberFilter(field_name='rule__id')
    start_time = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    end_time = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = DeviceCommand
        fields = [
            'device',
            'hardware_id',
            'status',
            'source',
            'rule',
            'start_time',
            'end_time',
        ]


class AutomationLogFilter(django_filters.FilterSet):
    rule = django_filters.NumberFilter(field_name='rule__id')
    room = django_filters.NumberFilter(field_name='room__id')
    device = django_filters.NumberFilter(field_name='device__id')
    execution_result = django_filters.CharFilter(field_name='execution_result', lookup_expr='iexact')
    action_type = django_filters.CharFilter(field_name='action_taken', lookup_expr='iexact')
    start_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_time = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = AutomationLog
        fields = [
            'rule',
            'room',
            'device',
            'execution_result',
            'action_type',
            'start_time',
            'end_time',
        ]
