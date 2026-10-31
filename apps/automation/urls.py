from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.automation.views import (
    AutomationRuleViewSet,
    DeviceCommandViewSet,
    ManualDeviceControlView,
    AutomationLogViewSet,
    AutomationEvaluateTriggerView,
)

app_name = 'automation'

router = DefaultRouter()
router.register(r'rules', AutomationRuleViewSet, basename='automation-rule')
router.register(r'commands', DeviceCommandViewSet, basename='device-command')
router.register(r'logs', AutomationLogViewSet, basename='automation-log')

urlpatterns = [
    path('manual-control/', ManualDeviceControlView.as_view(), name='manual-control'),
    path('evaluate/', AutomationEvaluateTriggerView.as_view(), name='automation-evaluate'),
] + router.urls
