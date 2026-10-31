from django.urls import path
from apps.energy.views import EnergySummaryAnalyticsView, BuildingComparisonAnalyticsView

app_name = 'analytics'

urlpatterns = [
    path('summary/', EnergySummaryAnalyticsView.as_view(), name='analytics-summary'),
    path('buildings/', BuildingComparisonAnalyticsView.as_view(), name='analytics-buildings'),
]
