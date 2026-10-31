import uuid
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from apps.automation.models import (
    AutomationRule,
    AutomationLog,
    DeviceCommand,
    CommandStatusChoices,
    CommandSourceChoices,
)
from apps.devices.models import Device, RelayChannel
from apps.automation.serializers import (
    AutomationRuleSerializer,
    DeviceCommandSerializer,
    ManualControlSerializer,
    CommandAcknowledgeSerializer,
    AutomationLogSerializer,
    AutomationEvaluateResponseSerializer,
)
from apps.automation.permissions import (
    IsAdminOrStaffAutomationAccess,
    CanDispatchManualControl,
)
from apps.automation.filters import (
    AutomationRuleFilter,
    DeviceCommandFilter,
    AutomationLogFilter,
)
from apps.automation.services import AutomationExecutionEngine

@extend_schema_view(
    list=extend_schema(summary="List Automation Rules", description="View all institutional automation rules across campus rooms and devices."),
    retrieve=extend_schema(summary="Get Automation Rule", description="Retrieve specific automation rule details and configuration."),
    create=extend_schema(summary="Create Automation Rule", description="Create an automated vacancy or energy threshold rule (Admin only)."),
    update=extend_schema(summary="Update Automation Rule", description="Modify condition, threshold, or target device (Admin only)."),
    destroy=extend_schema(summary="Delete Automation Rule", description="Remove an automation rule (Admin only)."),
)
class AutomationRuleViewSet(viewsets.ModelViewSet):
    queryset = AutomationRule.objects.select_related('room__floor__building', 'device', 'channel').all()
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAdminOrStaffAutomationAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AutomationRuleFilter
    search_fields = ['name', 'description', 'room__room_number', 'device__hardware_id']
    ordering_fields = ['name', 'condition_type', 'threshold_value', 'created_at']
    ordering = ['room', 'name']


@extend_schema_view(
    list=extend_schema(summary="List Device Commands", description="Audit history and queue status of dispatched device control commands."),
    retrieve=extend_schema(summary="Get Command Details", description="View specific command execution state and hardware acknowledgment."),
)
class DeviceCommandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceCommand.objects.select_related('device', 'channel', 'issued_by', 'rule').all()
    serializer_class = DeviceCommandSerializer
    permission_classes = [IsAdminOrStaffAutomationAccess]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DeviceCommandFilter
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    @extend_schema(
        summary="Acknowledge Device Command Execution",
        description="Records incoming hardware acknowledgment packet from ESP32 node. Updates physical channel reported state.",
        request=CommandAcknowledgeSerializer,
        responses={
            200: OpenApiResponse(description="Hardware acknowledgment recorded"),
            404: OpenApiResponse(description="Command not found"),
        }
    )
    @action(detail=False, methods=['post'], url_path='acknowledge', permission_classes=[CanDispatchManualControl])
    def acknowledge(self, request):
        serializer = CommandAcknowledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cmd_id = serializer.validated_data['command_id']
        reported_state = serializer.validated_data['reported_state']
        notes = serializer.validated_data.get('hardware_notes', '')

        try:
            command = DeviceCommand.objects.select_related('channel', 'device').get(command_id=cmd_id)
        except DeviceCommand.DoesNotExist:
            return Response({"detail": f"Command '{cmd_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        command.status = CommandStatusChoices.ACKNOWLEDGED
        command.hardware_ack_at = timezone.now()
        command.payload['hardware_ack_notes'] = notes
        command.save(update_fields=['status', 'hardware_ack_at', 'payload'])

        # Now and only now update the database relay channel state
        channel = command.channel
        channel.is_on = reported_state
        channel.save(update_fields=['is_on', 'updated_at'])

        return Response({
            "status": "ACKNOWLEDGED",
            "command_id": command.command_id,
            "device_hardware_id": command.device.hardware_id,
            "channel_index": channel.channel_index,
            "confirmed_relay_state": "ON" if channel.is_on else "OFF",
            "ack_timestamp": command.hardware_ack_at.isoformat()
        }, status=status.HTTP_200_OK)


class ManualDeviceControlView(APIView):
    """
    Issue validated manual ON/OFF command to an appliance or relay channel.
    """
    permission_classes = [CanDispatchManualControl]
    serializer_class = ManualControlSerializer

    @extend_schema(
        summary="Manual Device Control",
        description="Dispatch manual ON/OFF request for a device relay channel. Queues command and awaits hardware ACK.",
        request=ManualControlSerializer,
        responses={
            202: OpenApiResponse(description="Command queued for device"),
            400: OpenApiResponse(description="Validation error or safety locked"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = serializer.validated_data['device_instance']
        channel = serializer.validated_data['channel_instance']
        target_state = serializer.validated_data['target_state']
        reason = serializer.validated_data.get('reason', '')

        cmd = DeviceCommand.objects.create(
            device=device,
            channel=channel,
            source=CommandSourceChoices.MANUAL,
            issued_by=request.user,
            target_state=target_state,
            status=CommandStatusChoices.QUEUED,
            payload={
                'reason': reason,
                'requested_by': request.user.username
            }
        )

        AutomationLog.objects.create(
            device=device,
            room=device.room,
            command=cmd,
            action_taken=f"MANUAL_{'ON' if target_state else 'OFF'}",
            trigger_condition="MANUAL_DISPATCH",
            execution_result='COMMAND_QUEUED',
            details=f"User '{request.user.username}' dispatched manual {'ON' if target_state else 'OFF'} on Ch#{channel.channel_index}."
        )

        return Response({
            "command_id": cmd.command_id,
            "device_hardware_id": device.hardware_id,
            "channel_index": channel.channel_index,
            "requested_state": "ON" if target_state else "OFF",
            "current_reported_state": "ON" if channel.is_on else "OFF",
            "status": "QUEUED_FOR_DEVICE",
            "hardware_ack_received": False,
            "message": "Manual command accepted and queued for ESP32 dispatch. Confirmed state will update upon hardware ACK.",
            "dispatched_by": request.user.username,
            "timestamp": cmd.created_at.isoformat()
        }, status=status.HTTP_202_ACCEPTED)


@extend_schema_view(
    list=extend_schema(summary="List Automation Logs", description="Audit trail of rule evaluations, skipped triggers, and queued actions."),
    retrieve=extend_schema(summary="Get Automation Log Details", description="View specific automation execution record.")
)
class AutomationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AutomationLog.objects.select_related('rule', 'device', 'room', 'command').all()
    serializer_class = AutomationLogSerializer
    permission_classes = [IsAdminOrStaffAutomationAccess]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AutomationLogFilter
    ordering_fields = ['timestamp', 'execution_result']
    ordering = ['-timestamp']


class AutomationEvaluateTriggerView(APIView):
    """
    On-demand evaluation trigger for testing and periodic workers.
    """
    permission_classes = [CanDispatchManualControl]
    serializer_class = AutomationEvaluateResponseSerializer

    @extend_schema(
        summary="Evaluate Automation Rules",
        description="Executes rule-based automation engine cycle across all campus rooms and active devices.",
        responses={200: AutomationEvaluateResponseSerializer}
    )
    def post(self, request):
        logs = AutomationExecutionEngine.evaluate_all_rules()
        commands_count = sum(1 for log in logs if log.execution_result == 'COMMAND_QUEUED')

        return Response({
            "status": "CYCLE_COMPLETED",
            "rules_evaluated": AutomationRule.objects.filter(is_enabled=True).count(),
            "commands_generated": commands_count,
            "logs_created": len(logs)
        }, status=status.HTTP_200_OK)
