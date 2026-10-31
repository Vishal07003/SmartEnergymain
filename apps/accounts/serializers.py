from typing import Any, Dict
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.accounts.models import StaffProfile, RoleChoices

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer returning user credentials, profile information, and roles.
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
            'role': profile.role if profile else ('ADMIN' if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False) else 'STAFF'),
            'employee_id': profile.employee_id if profile else '',
            'department': profile.department if profile else '',
            'assigned_block': profile.assigned_block if profile else '',
            'notifications_enabled': profile.notifications_enabled if profile else True,
            'alert_push_enabled': profile.alert_push_enabled if profile else True,
        }
        data['user'] = user_data
        return data


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


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

