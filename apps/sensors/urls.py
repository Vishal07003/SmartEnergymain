from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.sensors.views import (
    SensorViewSet,
    TelemetryReadingViewSet,
    TelemetryIngestView,
    HeartbeatIngestView,
)

app_name = 'sensors'

router = DefaultRouter()
router.register(r'readings', TelemetryReadingViewSet, basename='telemetry-reading')
router.register(r'', SensorViewSet, basename='sensor')

urlpatterns = [
    path('ingest/telemetry/', TelemetryIngestView.as_view(), name='ingest-telemetry'),
    path('ingest/heartbeat/', HeartbeatIngestView.as_view(), name='ingest-heartbeat'),
] + router.urls
