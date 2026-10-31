from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.accounts.views import (
    CustomTokenObtainPairView,
    LogoutView,
    CurrentUserProfileView,
    ChangePasswordView,
)

# API v1 URL patterns
api_v1_patterns = [
    # Auth endpoints
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/me/', CurrentUserProfileView.as_view(), name='auth_me'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth_change_password'),
    
    # OpenAPI Documentation Schema
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='v1:schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='v1:schema'), name='redoc'),

    # Modular App Endpoints
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('rooms/', include('apps.rooms.urls', namespace='rooms')),
    path('devices/', include('apps.devices.urls', namespace='devices')),
    path('sensors/', include('apps.sensors.urls', namespace='sensors')),
    path('telemetry/', include('apps.sensors.urls', namespace='telemetry')),
    path('energy/', include('apps.energy.urls', namespace='energy')),
    path('alerts/', include('apps.alerts.urls', namespace='alerts')),
    path('analytics/', include('apps.analytics.urls', namespace='analytics')),
    path('automation/', include('apps.automation.urls', namespace='automation')),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include((api_v1_patterns, 'v1'), namespace='v1')),
]
