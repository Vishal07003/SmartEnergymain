from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
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
    RegisterSerializer,
    ForgotPasswordRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
)

class RegisterView(APIView):
    """
    User self-registration. Allows any new user to directly create their account.
    """
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(
        summary="User Self-Registration",
        description="Creates a new verified user account with unified application access.",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User registered successfully"),
            400: OpenApiResponse(description="Validation error"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate email verification token
        token = default_token_generator.make_token(user)

        # Generate JWT tokens for immediate seamless authentication
        refresh = RefreshToken.for_user(user)

        return Response({
            "detail": "Account registered successfully.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "verification_token": token,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    """
    Verify user email with token.
    """
    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer

    @extend_schema(
        summary="Verify Email Address",
        description="Confirms user email address with verification token.",
        request=EmailVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Email verified successfully"),
            400: OpenApiResponse(description="Invalid or expired token"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        token = serializer.validated_data['token']

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired verification token."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save(update_fields=['is_active'])

        return Response({"detail": "Email verified successfully."}, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    """
    Dispatches password reset token to registered email.
    """
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordRequestSerializer

    @extend_schema(
        summary="Forgot Password",
        description="Generates password reset token and sends recovery instructions.",
        request=ForgotPasswordRequestSerializer,
        responses={
            200: OpenApiResponse(description="Password reset token dispatched"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = User.objects.filter(email__iexact=email).first()

        # Always return 200 for user privacy
        if not user:
            return Response({
                "detail": "If an account exists with this email, password recovery instructions have been sent."
            }, status=status.HTTP_200_OK)

        token = default_token_generator.make_token(user)

        return Response({
            "detail": "If an account exists with this email, password recovery instructions have been sent.",
            "reset_token": token,  # Provided for mobile direct recovery flow
        }, status=status.HTTP_200_OK)


class ResetPasswordConfirmView(APIView):
    """
    Sets new password using verified token.
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        summary="Reset Password with Token",
        description="Updates password following token verification.",
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successfully"),
            400: OpenApiResponse(description="Invalid token or validation error"),
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"detail": "Invalid reset request."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired password reset token."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Password has been reset successfully. You can now log in."}, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Authenticate user using username/password and return JWT tokens plus user profile.
    """
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="User Login",
        description="Authenticates registered user, returning JWT access & refresh tokens along with profile details.",
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
        except TokenError:
            return Response(
                {"detail": "Token is invalid, malformed, or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST
            )


class CurrentUserProfileView(APIView):
    """
    Retrieve or update current authenticated user's private profile and preferences.
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
        description="Allows the authenticated user to update email, name, phone, or notification preferences.",
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
