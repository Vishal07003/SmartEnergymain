from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# API v1 URL patterns
api_v1_patterns = [
    # Auth endpoints
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # App routers will be wired here as each app is built
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('rooms/', include('apps.rooms.urls', namespace='rooms')),
    path('devices/', include('apps.devices.urls', namespace='devices')),
    path('energy/', include('apps.energy.urls', namespace='energy')),
    path('alerts/', include('apps.alerts.urls', namespace='alerts')),
    path('analytics/', include('apps.analytics.urls', namespace='analytics')),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include((api_v1_patterns, 'v1'), namespace='v1')),
]

