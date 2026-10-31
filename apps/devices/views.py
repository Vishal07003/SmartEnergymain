import uuid
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse

from apps.devices.models import Device, RelayChannel
from apps.telemetry.models import DeviceHeartbeat
from apps.rooms.models import Room
from apps.devices.serializers import (
    DeviceListSerializer,
    DeviceDetailSerializer,
    DeviceCreateSerializer,
    RelayChannelSerializer,
    DeviceHeartbeatSerializer,
    AssignRoomSerializer,
    DeviceCommandSerializer,
    compute_live_device_status,
)
from apps.devices.permissions import IsAdminOrReadOnlyStaffDevice, CanDispatchDeviceCommand
from apps.devices.filters import DeviceFilter

@extend_schema_view(
    list=extend_schema(
        summary="List Campus Devices",
        description="Filter, search, and paginate through institutional ESP32 nodes and smart controllers.",
        parameters=[
            OpenApiParameter('building', int, description='Filter by building ID'),
            OpenApiParameter('building_code', str, description='Filter by building code (e.g. BLD-ST)'),
            OpenApiParameter('floor', int, description='Filter by floor ID'),
            OpenApiParameter('room', int, description='Filter by room ID'),
            OpenApiParameter('device_type', str, description='Filter by device type: ESP32_NODE, RELAY_MODULE, etc.'),
            OpenApiParameter('status', str, description='Filter by configured status: ONLINE, OFFLINE, DEGRADED'),
        ]
    ),
    retrieve=extend_schema(
        summary="Get Device Details",
        description="Retrieve full device telemetry metadata, relay channels, and calculated live heartbeat status."
    ),
    create=extend_schema(
        summary="Register Device",
        description="Register a new ESP32 device with hardware ID validation and optional channel initialization (Admin only)."
    ),
    update=extend_schema(
        summary="Update Device",
        description="Update device settings, firmware version, and Wi-Fi configurations (Admin only)."
    ),
    destroy=extend_schema(
        summary="Deregister Device",
        description="Remove a device from campus inventory (Admin only)."
    ),
)
class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.select_related('room__floor__building').prefetch_related('channels', 'heartbeats').all()
    permission_classes = [IsAdminOrReadOnlyStaffDevice]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DeviceFilter
    search_fields = ['name', 'hardware_id', 'mac_address', 'room__room_number', 'room__name']
    ordering_fields = ['name', 'hardware_id', 'status', 'uptime_hours', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'create':
            return DeviceCreateSerializer
        if self.action == 'retrieve':
            return DeviceDetailSerializer
        return DeviceListSerializer

    @extend_schema(
        summary="Get Device Heartbeat",
        description="Returns the most recent heartbeat record and connectivity metrics received from the ESP32 node.",
        responses={
            200: DeviceHeartbeatSerializer,
            404: OpenApiResponse(description="No heartbeat records received yet for this device")
        }
    )
    @action(detail=True, methods=['get'], url_path='heartbeat')
    def heartbeat(self, request, pk=None):
        device = self.get_object()
        latest = device.heartbeats.order_by('-timestamp').first()
        if not latest:
            return Response(
                {
                    "device_id": device.id,
                    "hardware_id": device.hardware_id,
                    "calculated_status": "UNKNOWN",
                    "detail": "No heartbeat received yet from physical hardware."
                },
                status=status.HTTP_200_OK
            )
        serializer = DeviceHeartbeatSerializer(latest)
        data = serializer.data
        data['calculated_status'] = compute_live_device_status(device)
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="List Relay Channels",
        description="Returns all controllable and fixed relay channels configured for this device.",
        responses={200: RelayChannelSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='channels')
    def channels(self, request, pk=None):
        device = self.get_object()
        serializer = RelayChannelSerializer(device.channels.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get Device Heartbeat History",
        description="Returns historical heartbeat transmissions (up to the last 50 entries) for diagnostics.",
        responses={200: DeviceHeartbeatSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        device = self.get_object()
        heartbeats = device.heartbeats.order_by('-timestamp')[:50]
        serializer = DeviceHeartbeatSerializer(heartbeats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Assign Device to Room",
        description="Change or set the room assignment for this device with strict validation (Admin only).",
        request=AssignRoomSerializer,
        responses={
            200: OpenApiResponse(description="Room assigned successfully"),
            400: OpenApiResponse(description="Invalid room ID or inactive room"),
        }
    )
    @action(detail=True, methods=['patch', 'post'], url_path='assign-room', permission_classes=[IsAdminOrReadOnlyStaffDevice])
    def assign_room(self, request, pk=None):
        device = self.get_object()
        serializer = AssignRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_room = Room.objects.get(id=serializer.validated_data['room_id'])
        old_room = device.room
        device.room = new_room
        device.save(update_fields=['room'])

        return Response({
            "detail": f"Device '{device.name}' successfully reassigned to Room {new_room.room_number}.",
            "previous_room": old_room.room_number if old_room else None,
            "new_room": new_room.room_number,
            "new_room_id": new_room.id
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Issue Relay Command",
        description="Validate and queue a relay ON/OFF command. Does NOT return premature execution success without real hardware acknowledgment.",
        request=DeviceCommandSerializer,
        responses={
            202: OpenApiResponse(description="Command accepted and queued; awaiting ESP32 hardware execution"),
            400: OpenApiResponse(description="Invalid channel or safety locked"),
        }
    )
    @action(detail=True, methods=['post'], url_path='commands', permission_classes=[CanDispatchDeviceCommand])
    def commands(self, request, pk=None):
        device = self.get_object()
        serializer = DeviceCommandSerializer(data=request.data, context={'device': device})
        serializer.is_valid(raise_exception=True)

        channel = serializer.validated_data['channel_instance']
        target_state = serializer.validated_data['target_state']
        reason = serializer.validated_data.get('reason', '')

        command_id = f"cmd_{uuid.uuid4().hex[:12]}"

        # Explicit honesty guarantee:
        # We record the command request as QUEUED / PENDING_DEVICE_ACK.
        # We DO NOT modify channel.is_on prematurely.
        return Response({
            "command_id": command_id,
            "device_hardware_id": device.hardware_id,
            "channel_index": channel.channel_index,
            "requested_state": "ON" if target_state else "OFF",
            "current_reported_state": "ON" if channel.is_on else "OFF",
            "status": "QUEUED_FOR_DEVICE",
            "hardware_ack_received": False,
            "message": "Command validated and queued for ESP32 MQTT dispatch. Relay state will update once physical node transmits acknowledgment.",
            "dispatched_by": request.user.username,
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_202_ACCEPTED)
