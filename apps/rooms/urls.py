from rest_framework.routers import DefaultRouter
from apps.rooms.views import BuildingViewSet, FloorViewSet, RoomViewSet

app_name = 'rooms'

router = DefaultRouter()
router.register(r'buildings', BuildingViewSet, basename='building')
router.register(r'floors', FloorViewSet, basename='floor')
router.register(r'', RoomViewSet, basename='room')

urlpatterns = router.urls
