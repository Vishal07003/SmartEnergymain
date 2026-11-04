from rest_framework import permissions

class IsAdminOrReadOnlyStaffSensor(permissions.BasePermission):
    """
    Unified access: All authenticated users can view, register, and manage sensors.
    """
    message = 'Authentication required to manage environmental sensors.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class CanIngestTelemetry(permissions.BasePermission):
    """
    Controls access to telemetry & heartbeat ingestion endpoints.
    Allows authenticated users, background processes, or edge devices.
    """
    message = 'Authentication required for telemetry ingestion.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
