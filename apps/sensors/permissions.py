from rest_framework import permissions

class IsAdminOrReadOnlyStaffSensor(permissions.BasePermission):
    """
    Staff can view sensors and readings.
    Only Admins can register, update, delete or reassign sensors.
    """
    message = 'Administrative credentials are required to modify sensor configurations.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if user.is_staff or user.is_superuser:
            return True

        profile = getattr(user, 'staff_profile', None)
        return bool(profile and profile.role == 'ADMIN')


class CanIngestTelemetry(permissions.BasePermission):
    """
    Controls access to telemetry & heartbeat ingestion endpoints.
    Allows authenticated institutional admin/staff, or services possessing valid auth headers.
    """
    message = 'Authentication required for telemetry ingestion.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated)
