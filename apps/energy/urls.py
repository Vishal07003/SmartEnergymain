from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.energy.views import (
    EnergyReadingViewSet,
    DailyEnergyAggregationViewSet,
    EnergyIngestView,
    EnergySummaryAnalyticsView,
    BuildingComparisonAnalyticsView,
)

app_name = 'energy'

router = DefaultRouter()
router.register(r'readings', EnergyReadingViewSet, basename='energy-reading')
router.register(r'daily', DailyEnergyAggregationViewSet, basename='daily-aggregation')

urlpatterns = [
    path('ingest/', EnergyIngestView.as_view(), name='energy-ingest'),
    path('analytics/summary/', EnergySummaryAnalyticsView.as_view(), name='energy-summary'),
    path('analytics/buildings/', BuildingComparisonAnalyticsView.as_view(), name='energy-buildings-comparison'),
] + router.urls
