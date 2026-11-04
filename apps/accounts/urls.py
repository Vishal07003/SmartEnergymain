from django.urls import path
from apps.accounts.views import (
    RegisterView,
    VerifyEmailView,
    ForgotPasswordView,
    ResetPasswordConfirmView,
    CustomTokenObtainPairView,
    LogoutView,
    CurrentUserProfileView,
    ChangePasswordView,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('reset-password/', ResetPasswordConfirmView.as_view(), name='auth-reset-password'),
    path('profile/', CurrentUserProfileView.as_view(), name='user-profile'),
]
