from rest_framework import permissions

class IsAdminOrReadOnlyStaffEnergy(permissions.BasePermission):
    """
    Unified access: All authenticated users can view campus energy data and analytics.
    """
    message = 'Authentication required to view campus energy telemetry.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class CanIngestEnergyReading(permissions.BasePermission):
    """
    Controls access to energy ingestion endpoints.
    Allows authenticated users, edge devices, or verified services.
    """
    message = 'Authentication required for energy reading ingestion.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
