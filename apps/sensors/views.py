from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse

from apps.sensors.models import Sensor
from apps.telemetry.models import TelemetryReading, DeviceHeartbeat
from apps.devices.models import Device
from apps.sensors.serializers import (
    SensorListSerializer,
    SensorDetailSerializer,
    SensorCreateUpdateSerializer,
    TelemetryReadingSerializer,
    TelemetryIngestSerializer,
    HeartbeatIngestSerializer,
)
from apps.sensors.permissions import IsAdminOrReadOnlyStaffSensor, CanIngestTelemetry
from apps.sensors.filters import SensorFilter, TelemetryReadingFilter

@extend_schema_view(
    list=extend_schema(summary="List Sensors", description="Filter and search all campus sensors (PIR, Temp, Lux, etc.)."),
    retrieve=extend_schema(summary="Get Sensor Details", description="Retrieve sensor configuration, room assignment, and latest telemetry."),
    create=extend_schema(summary="Register Sensor", description="Register a new sensor and map it to a room & device (Admin only)."),
    update=extend_schema(summary="Update Sensor", description="Update sensor metadata, active state, or model (Admin only)."),
    destroy=extend_schema(summary="Deregister Sensor", description="Remove a sensor (Admin only)."),
)
class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.select_related('room__floor__building', 'device').prefetch_related('readings').all()
    permission_classes = [IsAdminOrReadOnlyStaffSensor]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SensorFilter
    search_fields = ['sensor_type', 'sensor_model', 'room__room_number', 'device__hardware_id']
    ordering_fields = ['sensor_type', 'created_at', 'room__room_number']
    ordering = ['room__room_number', 'sensor_type']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SensorCreateUpdateSerializer
        if self.action == 'retrieve':
            return SensorDetailSerializer
        return SensorListSerializer

    @extend_schema(
        summary="Get Latest Sensor Reading",
        description="Returns the most recent measured value for this specific sensor.",
        responses={
            200: TelemetryReadingSerializer,
            404: OpenApiResponse(description="No telemetry readings recorded for this sensor yet"),
        }
    )
    @action(detail=True, methods=['get'], url_path='latest')
    def latest(self, request, pk=None):
        sensor = self.get_object()
        latest_reading = sensor.readings.order_by('-timestamp').first()
        if not latest_reading:
            return Response(
                {"detail": "No telemetry readings recorded for this sensor yet."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = TelemetryReadingSerializer(latest_reading)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get Sensor Readings History",
        description="Paginated or time-bounded telemetry history for this sensor.",
        parameters=[
            OpenApiParameter('start_time', str, description='ISO 8601 start timestamp filter'),
            OpenApiParameter('end_time', str, description='ISO 8601 end timestamp filter'),
        ],
        responses={200: TelemetryReadingSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        sensor = self.get_object()
        readings = sensor.readings.all()

        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        if start_time:
            readings = readings.filter(timestamp__gte=start_time)
        if end_time:
            readings = readings.filter(timestamp__lte=end_time)

        page = self.paginate_queryset(readings)
        if page is not None:
            serializer = TelemetryReadingSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TelemetryReadingSerializer(readings[:100], many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List Telemetry Readings",
        description="Query and filter all measured telemetry across campus by sensor type, room, device, or time range."
    ),
    retrieve=extend_schema(summary="Get Telemetry Reading Record", description="View a specific telemetry measurement.")
)
class TelemetryReadingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TelemetryReading.objects.select_related('sensor__room', 'sensor__device').all()
    serializer_class = TelemetryReadingSerializer
    permission_classes = [IsAdminOrReadOnlyStaffSensor]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = TelemetryReadingFilter
    ordering_fields = ['timestamp', 'value']
    ordering = ['-timestamp']


class TelemetryIngestView(APIView):
    """
    Ingest measured telemetry from authenticated ESP32 nodes or gateways.
    Strictly verifies device-to-sensor mapping before saving.
    """
    permission_classes = [CanIngestTelemetry]

    @extend_schema(
        summary="Ingest Sensor Telemetry",
        description="Securely ingest physical sensor measurements. Rejects unregistered or mismatched device-sensor combinations.",
        request=TelemetryIngestSerializer,
        responses={
            201: OpenApiResponse(description="Telemetry reading recorded successfully"),
            400: OpenApiResponse(description="Validation error or mismatched sensor mapping"),
            401: OpenApiResponse(description="Unauthorized"),
        }
    )
    def post(self, request):
        serializer = TelemetryIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sensor = serializer.validated_data['sensor_instance']
        value = serializer.validated_data['value']
        raw_payload = serializer.validated_data.get('raw_payload', {})

        reading = TelemetryReading.objects.create(
            sensor=sensor,
            value=value,
            raw_payload=raw_payload
        )

        return Response({
            "status": "RECORDED",
            "reading_id": reading.id,
            "sensor_id": sensor.id,
            "sensor_type": sensor.sensor_type,
            "value": reading.value,
            "timestamp": reading.timestamp.isoformat()
        }, status=status.HTTP_201_CREATED)


class HeartbeatIngestView(APIView):
    """
    Ingest periodic heartbeat transmissions from ESP32 nodes.
    Prevents duplicate writes within 10 seconds to guard against transmission bursts.
    """
    permission_classes = [CanIngestTelemetry]

    @extend_schema(
        summary="Ingest Device Heartbeat",
        description="Ingest heartbeat metrics (voltage, current, Wi-Fi RSSI, uptime) from authorized ESP32 hardware.",
        request=HeartbeatIngestSerializer,
        responses={
            201: OpenApiResponse(description="Heartbeat recorded"),
            200: OpenApiResponse(description="Duplicate heartbeat suppressed"),
            400: OpenApiResponse(description="Invalid hardware ID or measurements"),
        }
    )
    def post(self, request):
        serializer = HeartbeatIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = serializer.validated_data['device_instance']
        voltage = serializer.validated_data['voltage']
        current = serializer.validated_data['current']
        power_watts = serializer.validated_data['power_watts']
        wifi_rssi = serializer.validated_data['wifi_rssi']
        uptime_seconds = serializer.validated_data['uptime_seconds']

        # Guard against accidental transmission burst duplicates (within 10 seconds)
        ten_seconds_ago = timezone.now() - timedelta(seconds=10)
        recent = DeviceHeartbeat.objects.filter(device=device, timestamp__gte=ten_seconds_ago).first()
        if recent:
            return Response({
                "status": "SUPPRESSED_BURST_DUPLICATE",
                "message": "Heartbeat received within debounce window (10s); state maintained.",
                "device_hardware_id": device.hardware_id,
            }, status=status.HTTP_200_OK)

        heartbeat = DeviceHeartbeat.objects.create(
            device=device,
            voltage=voltage,
            current=current,
            power_watts=power_watts,
            wifi_rssi=wifi_rssi,
            uptime_seconds=uptime_seconds
        )

        # Update cached device metadata
        device.wifi_rssi = wifi_rssi
        device.uptime_hours = uptime_seconds // 3600
        device.save(update_fields=['wifi_rssi', 'uptime_hours', 'last_communication_time'])

        return Response({
            "status": "HEARTBEAT_RECORDED",
            "heartbeat_id": heartbeat.id,
            "device_hardware_id": device.hardware_id,
            "timestamp": heartbeat.timestamp.isoformat()
        }, status=status.HTTP_201_CREATED)
