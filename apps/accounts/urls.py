from django.urls import path
from apps.accounts.views import (
    CustomTokenObtainPairView,
    LogoutView,
    CurrentUserProfileView,
    ChangePasswordView,
)

app_name = 'accounts'

urlpatterns = [
    path('profile/', CurrentUserProfileView.as_view(), name='staff-profile'),
]
