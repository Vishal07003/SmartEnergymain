from rest_framework.routers import DefaultRouter
from apps.devices.views import DeviceViewSet

app_name = 'devices'

router = DefaultRouter()
router.register(r'', DeviceViewSet, basename='device')

urlpatterns = router.urls
