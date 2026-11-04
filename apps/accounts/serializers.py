from typing import Any, Dict
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.accounts.models import StaffProfile, RoleChoices

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer returning user credentials, profile information, and unified permissions.
    """
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = dict(super().validate(attrs))
        user: Any = self.user
        if not user:
            return data

        profile = getattr(user, 'staff_profile', None)

        user_data: Dict[str, Any] = {
            'id': getattr(user, 'id', None),
            'username': getattr(user, 'username', ''),
            'email': getattr(user, 'email', ''),
            'first_name': getattr(user, 'first_name', ''),
            'last_name': getattr(user, 'last_name', ''),
            'is_staff': getattr(user, 'is_staff', False),
            'is_superuser': getattr(user, 'is_superuser', False),
            'is_active': getattr(user, 'is_active', True),
            'role': profile.role if profile else ('ADMIN' if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False) else 'STAFF'),
            'employee_id': profile.employee_id if profile else f"USR-{getattr(user, 'id', '0')}",
            'department': profile.department if profile else 'Campus Facility',
            'assigned_block': profile.assigned_block if profile else 'Campus Main',
            'notifications_enabled': profile.notifications_enabled if profile else True,
            'alert_push_enabled': profile.alert_push_enabled if profile else True,
        }
        data['user'] = user_data
        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    department = serializers.CharField(required=False, allow_blank=True, default='Campus Facility')
    phone_number = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'password_confirm',
            'department',
            'phone_number',
        ]

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError('Email address is required.')
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with that email already exists.')
        return value.lower()

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('A user with that username already exists.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        department = validated_data.pop('department', 'Campus Facility')
        phone_number = validated_data.pop('phone_number', '')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_active=True,  # Activated upon registration
        )

        StaffProfile.objects.create(
            user=user,
            employee_id=f"USR-{user.id:04d}",
            department=department,
            phone_number=phone_number,
            role=RoleChoices.STAFF,
            assigned_block='Campus Main',
            notifications_enabled=True,
            alert_push_enabled=True,
        )

        return user


class StaffProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffProfile
        fields = [
            'employee_id',
            'department',
            'phone_number',
            'role',
            'assigned_block',
            'notifications_enabled',
            'alert_push_enabled',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['employee_id', 'role', 'created_at', 'updated_at']


class CurrentUserProfileSerializer(serializers.ModelSerializer):
    profile = StaffProfileSerializer(source='staff_profile', required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_staff',
            'is_superuser',
            'profile',
        ]
        read_only_fields = ['id', 'username', 'is_staff', 'is_superuser']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('staff_profile', None)
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()

        if profile_data:
            profile = getattr(instance, 'staff_profile', None)
            if profile:
                profile.phone_number = profile_data.get('phone_number', profile.phone_number)
                profile.department = profile_data.get('department', profile.department)
                profile.assigned_block = profile_data.get('assigned_block', profile.assigned_block)
                profile.notifications_enabled = profile_data.get('notifications_enabled', profile.notifications_enabled)
                profile.alert_push_enabled = profile_data.get('alert_push_enabled', profile.alert_push_enabled)
                profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is not correct.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'The new passwords do not match.'})

        user = self.context['request'].user
        validate_password(attrs['new_password'], user)
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'The passwords do not match.'})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)
