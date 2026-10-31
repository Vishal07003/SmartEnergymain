from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.alerts.views import AIAlertViewSet, AlertSummaryView, AnomalyScanView

app_name = 'alerts'

router = DefaultRouter()
router.register(r'', AIAlertViewSet, basename='alert')

urlpatterns = [
    path('summary/', AlertSummaryView.as_view(), name='alert-summary'),
    path('scan/', AnomalyScanView.as_view(), name='alert-scan'),
] + router.urls
