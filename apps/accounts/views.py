from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    CurrentUserProfileSerializer,
    ChangePasswordSerializer,
    LogoutSerializer,
)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Authenticate staff or admin using username/password and return JWT tokens plus user profile.
    """
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="User Login",
        description="Authenticates staff or administrator, returning JWT access & refresh tokens along with institutional role details.",
        responses={
            200: CustomTokenObtainPairSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    """
    Invalidate and blacklist the provided refresh token.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        summary="User Logout",
        description="Blacklists the provided JWT refresh token, preventing further token renewals.",
        request=LogoutSerializer,
        responses={
            200: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(description="Invalid or expired token"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh_token = serializer.validated_data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out and session revoked."},
                status=status.HTTP_200_OK
            )
        except TokenError as e:
            return Response(
                {"detail": "Token is invalid, malformed, or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST
            )


class CurrentUserProfileView(APIView):
    """
    Retrieve or update current authenticated user's profile and preferences.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Current User Profile",
        description="Returns detailed profile, department, block, and preference settings for the authenticated user.",
        responses={200: CurrentUserProfileSerializer}
    )
    def get(self, request):
        serializer = CurrentUserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update Current User Profile",
        description="Allows the authenticated staff member to update email, name, phone, or notification preferences.",
        request=CurrentUserProfileSerializer,
        responses={200: CurrentUserProfileSerializer}
    )
    def patch(self, request):
        serializer = CurrentUserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """
    Change password for the authenticated user with old password verification.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change Password",
        description="Securely changes the user's password following Django's password validation rules.",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully"),
            400: OpenApiResponse(description="Validation error or incorrect old password"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been updated successfully."},
            status=status.HTTP_200_OK
        )

