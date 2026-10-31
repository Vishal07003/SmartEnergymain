from rest_framework import permissions

class IsAdminOrReadOnlyStaffEnergy(permissions.BasePermission):
    """
    Staff can view energy data and analytics.
    Only Admins or authenticated ingestion sources can submit or manage records.
    """
    message = 'Administrative credentials or ingestion service authority required.'

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


class CanIngestEnergyReading(permissions.BasePermission):
    """
    Controls access to energy ingestion endpoints.
    Allows authenticated institutional staff/admin or edge devices.
    """
    message = 'Authentication required for energy reading ingestion.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated)

