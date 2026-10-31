from django.utils import timezone
from django.db.models import Count, Sum
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse

from apps.alerts.models import AIAlert, AlertSeverityChoices
from apps.alerts.serializers import (
    AIAlertListSerializer,
    AIAlertDetailSerializer,
    AlertActionResponseSerializer,
    AlertSummarySerializer,
    AnomalyScanResponseSerializer,
)
from apps.alerts.permissions import IsAdminOrStaffAlertAccess
from apps.alerts.filters import AlertFilter
from apps.alerts.services import AnomalyDetectionService
from apps.rooms.models import Room

@extend_schema_view(
    list=extend_schema(summary="List Alerts", description="Search, filter, and paginate through campus energy anomalies and system alerts."),
    retrieve=extend_schema(summary="Get Alert Details", description="Retrieve detailed alert diagnoses, possible causes, and recommended actions."),
)
class AIAlertViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AIAlert.objects.select_related('room__floor__building', 'device').all()
    permission_classes = [IsAdminOrStaffAlertAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AlertFilter
    search_fields = ['title', 'description', 'room__room_number', 'device__hardware_id']
    ordering_fields = ['timestamp', 'severity', 'power_wastage_estimate_watts']
    ordering = ['-timestamp']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AIAlertDetailSerializer
        return AIAlertListSerializer

    @extend_schema(
        summary="Acknowledge Alert",
        description="Mark an alert as acknowledged by the current staff member/administrator.",
        responses={200: AlertActionResponseSerializer}
    )
    @action(detail=True, methods=['patch', 'post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        user_display = request.user.get_full_name() or request.user.username
        alert.is_acknowledged = True
        alert.acknowledged_by = user_display
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at'])

        return Response({
            "status": "ACKNOWLEDGED",
            "alert_id": alert.id,
            "action": "acknowledge",
            "actor": user_display,
            "timestamp": alert.acknowledged_at.isoformat()
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Resolve Alert",
        description="Mark an anomaly or system alert as resolved and closed.",
        responses={200: AlertActionResponseSerializer}
    )
    @action(detail=True, methods=['patch', 'post'], url_path='resolve')
    def resolve(self, request, pk=None):
        alert = self.get_object()
        user_display = request.user.get_full_name() or request.user.username
        alert.is_resolved = True
        alert.resolved_by = user_display
        alert.resolved_at = timezone.now()
        alert.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at'])

        return Response({
            "status": "RESOLVED",
            "alert_id": alert.id,
            "action": "resolve",
            "actor": user_display,
            "timestamp": alert.resolved_at.isoformat()
        }, status=status.HTTP_200_OK)


class AlertSummaryView(APIView):
    """
    Returns campus-wide count of active unresolved alerts categorized by severity.
    """
    permission_classes = [IsAdminOrStaffAlertAccess]

    @extend_schema(
        summary="Alerts Summary",
        description="Returns counts of active, unresolved alerts segmented by CRITICAL, HIGH, MEDIUM, and LOW severity.",
        responses={200: AlertSummarySerializer}
    )
    def get(self, request):
        unresolved = AIAlert.objects.filter(is_resolved=False)

        critical_count = unresolved.filter(severity=AlertSeverityChoices.CRITICAL).count()
        high_count = unresolved.filter(severity=AlertSeverityChoices.HIGH).count()
        medium_count = unresolved.filter(severity__in=[AlertSeverityChoices.MEDIUM, AlertSeverityChoices.WARNING]).count()
        low_count = unresolved.filter(severity__in=[AlertSeverityChoices.LOW, AlertSeverityChoices.INFO]).count()

        total_wastage = unresolved.aggregate(total=Sum('power_wastage_estimate_watts'))['total'] or 0.0

        # Category breakdown
        breakdown = {}
        counts = unresolved.values('category').annotate(count=Count('id'))
        for item in counts:
            breakdown[item['category']] = item['count']

        return Response({
            "total_unresolved": unresolved.count(),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "total_power_wastage_watts": round(total_wastage, 2),
            "category_breakdown": breakdown
        }, status=status.HTTP_200_OK)


class AnomalyScanView(APIView):
    """
    Triggers rule-based anomaly detection scan across rooms and devices.
    """
    permission_classes = [IsAdminOrStaffAlertAccess]
    serializer_class = AnomalyScanResponseSerializer

    @extend_schema(
        summary="Trigger Anomaly Scan",
        description="Executes rule-based energy and device anomaly detection, evaluating vacant room wastage and device heartbeats.",
        responses={200: AnomalyScanResponseSerializer}
    )
    def post(self, request):
        rooms = Room.objects.filter(is_active=True)
        detected_alerts = []

        for room in rooms:
            alert = AnomalyDetectionService.evaluate_room_energy_anomaly(room)
            if alert:
                detected_alerts.append(alert.id)
            temp_alert = AnomalyDetectionService.evaluate_temperature_sensor_anomaly(room)
            if temp_alert:
                detected_alerts.append(temp_alert.id)

        return Response({
            "status": "SCAN_COMPLETED",
            "rooms_scanned": rooms.count(),
            "new_alerts_created": len(detected_alerts),
            "alert_ids": detected_alerts,
            "method": "RULE_BASED"
        }, status=status.HTTP_200_OK)
