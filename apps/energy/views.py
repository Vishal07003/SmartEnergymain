from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Max, Count
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse

from apps.energy.models import EnergyReading, DailyEnergyAggregation
from apps.rooms.models import Room, Building
from apps.energy.serializers import (
    EnergyReadingSerializer,
    EnergyReadingIngestSerializer,
    DailyEnergyAggregationSerializer,
    CampusEnergySummarySerializer,
    BuildingComparisonResponseSerializer,
)
from apps.energy.permissions import IsAdminOrReadOnlyStaffEnergy, CanIngestEnergyReading
from apps.energy.filters import EnergyReadingFilter, DailyEnergyAggregationFilter

@extend_schema_view(
    list=extend_schema(summary="List Energy Readings", description="Query telemetry energy measurements across rooms and buildings."),
    retrieve=extend_schema(summary="Get Energy Reading", description="Retrieve single energy measurement record."),
)
class EnergyReadingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EnergyReading.objects.select_related('room__floor__building', 'device').all()
    serializer_class = EnergyReadingSerializer
    permission_classes = [IsAdminOrReadOnlyStaffEnergy]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = EnergyReadingFilter
    ordering_fields = ['timestamp', 'active_power_watts', 'energy_kwh']
    ordering = ['-timestamp']

    @extend_schema(
        summary="Get Latest Room Energy Reading",
        description="Returns the single most recent energy measurement recorded for a specified room ID.",
        parameters=[OpenApiParameter('room_id', int, required=True, description='Room ID')],
        responses={200: EnergyReadingSerializer, 404: OpenApiResponse(description="No readings found for room")}
    )
    @action(detail=False, methods=['get'], url_path='latest-by-room')
    def latest_by_room(self, request):
        room_id = request.query_params.get('room_id')
        if not room_id:
            return Response({"detail": "room_id query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        reading = EnergyReading.objects.filter(room_id=room_id).order_by('-timestamp', '-id').first()
        if not reading:
            return Response({"detail": f"No energy readings found for room ID {room_id}."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EnergyReadingSerializer(reading)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(summary="List Daily Energy Aggregations", description="Query daily aggregated kWh and peak power by room."),
    retrieve=extend_schema(summary="Get Daily Aggregation", description="Retrieve daily summary record.")
)
class DailyEnergyAggregationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyEnergyAggregation.objects.select_related('room__floor__building').all()
    serializer_class = DailyEnergyAggregationSerializer
    permission_classes = [IsAdminOrReadOnlyStaffEnergy]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DailyEnergyAggregationFilter
    ordering_fields = ['date', 'total_kwh', 'peak_power_watts']
    ordering = ['-date']


class EnergyIngestView(APIView):
    """
    Ingest verified instantaneous power and electrical measurements from smart meters or CT clamps.
    """
    permission_classes = [CanIngestEnergyReading]

    @extend_schema(
        summary="Ingest Energy Reading",
        description="Record validated electrical power telemetry for an institutional room/device.",
        request=EnergyReadingIngestSerializer,
        responses={
            201: OpenApiResponse(description="Energy reading recorded"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
        }
    )
    def post(self, request):
        serializer = EnergyReadingIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room = serializer.validated_data['room_instance']
        device = serializer.validated_data['device_instance']
        voltage = serializer.validated_data['voltage_volts']
        current = serializer.validated_data['current_amps']
        active_power = serializer.validated_data['active_power_watts']
        pf = serializer.validated_data['power_factor']
        frequency = serializer.validated_data['frequency_hz']
        energy_kwh = serializer.validated_data['energy_kwh']

        reading = EnergyReading.objects.create(
            room=room,
            device=device,
            voltage_volts=voltage,
            current_amps=current,
            active_power_watts=active_power,
            power_factor=pf,
            frequency_hz=frequency,
            energy_kwh=energy_kwh
        )

        return Response({
            "status": "RECORDED",
            "reading_id": reading.id,
            "room_number": room.room_number,
            "active_power_watts": reading.active_power_watts,
            "timestamp": reading.timestamp.isoformat()
        }, status=status.HTTP_201_CREATED)


class EnergySummaryAnalyticsView(APIView):
    """
    Provides aggregated institutional energy metrics across custom horizons (day, week, month, range).
    """
    permission_classes = [IsAdminOrReadOnlyStaffEnergy]

    @extend_schema(
        summary="Campus Energy Analytics Summary",
        description="Returns total kWh consumption, average power, peak power, and room breakdowns for institutional audits.",
        parameters=[
            OpenApiParameter('building_id', int, required=False, description='Filter by building ID'),
            OpenApiParameter('room_id', int, required=False, description='Filter by room ID'),
            OpenApiParameter('days', int, required=False, default=7, description='Number of trailing days (default: 7)'),
        ],
        responses={200: CampusEnergySummarySerializer}
    )
    def get(self, request):
        building_id = request.query_params.get('building_id')
        room_id = request.query_params.get('room_id')
        days = int(request.query_params.get('days', 7))

        start_date = timezone.now().date() - timedelta(days=days)
        queryset = DailyEnergyAggregation.objects.filter(date__gte=start_date)

        if building_id:
            queryset = queryset.filter(room__floor__building_id=building_id)
        if room_id:
            queryset = queryset.filter(room_id=room_id)

        aggregates = queryset.aggregate(
            total_kwh=Sum('total_kwh'),
            peak_watts=Max('peak_power_watts'),
            rooms_count=Count('room', distinct=True)
        )

        total_kwh = aggregates['total_kwh'] or 0.0
        peak_watts = aggregates['peak_watts'] or 0.0
        rooms_count = aggregates['rooms_count'] or 0

        # Compute average power across hours in horizon (kW * 1000 / total_hours)
        total_hours = max(1, days * 24)
        avg_watts = (total_kwh * 1000.0) / total_hours

        # Room-level distribution
        room_distribution = []
        room_group = queryset.values('room__room_number', 'room__name').annotate(
            room_kwh=Sum('total_kwh')
        ).order_by('-room_kwh')[:10]

        for item in room_group:
            room_distribution.append({
                'room_number': item['room__room_number'],
                'room_name': item['room__name'],
                'total_kwh': round(item['room_kwh'] or 0.0, 2)
            })

        return Response({
            "start_date": str(start_date),
            "end_date": str(timezone.now().date()),
            "days_evaluated": days,
            "total_consumption_kwh": round(total_kwh, 2),
            "average_power_watts": round(avg_watts, 2),
            "peak_power_watts": round(peak_watts, 2),
            "active_monitoring_rooms": rooms_count,
            "room_distribution": room_distribution,
            "waste_estimate_notice": "Estimates and savings are derived strictly from documented baseline threshold assumptions and confirmed idle room states."
        }, status=status.HTTP_200_OK)


class BuildingComparisonAnalyticsView(APIView):
    """
    Compares energy consumption and efficiency across all campus buildings.
    """
    permission_classes = [IsAdminOrReadOnlyStaffEnergy]

    @extend_schema(
        summary="Building Energy Comparison",
        description="Compares cumulative energy consumption across all campus buildings for the designated trailing period.",
        parameters=[
            OpenApiParameter('days', int, required=False, default=30, description='Trailing period in days (default: 30)'),
        ],
        responses={200: BuildingComparisonResponseSerializer}
    )
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)

        buildings = Building.objects.all()
        comparison = []

        for bld in buildings:
            aggregates = DailyEnergyAggregation.objects.filter(
                room__floor__building=bld,
                date__gte=start_date
            ).aggregate(
                total_kwh=Sum('total_kwh'),
                peak_watts=Max('peak_power_watts')
            )
            comparison.append({
                'building_id': bld.id,
                'building_name': bld.name,
                'building_code': bld.code,
                'total_kwh': round(aggregates['total_kwh'] or 0.0, 2),
                'peak_power_watts': round(aggregates['peak_watts'] or 0.0, 2),
            })

        return Response({
            "period_days": days,
            "since_date": str(start_date),
            "buildings": comparison
        }, status=status.HTTP_200_OK)
