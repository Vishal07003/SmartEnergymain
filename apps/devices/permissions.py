from rest_framework import permissions

class IsAdminOrReadOnlyStaffDevice(permissions.BasePermission):
    """
    Staff can view devices, status, channels, and history (GET, HEAD, OPTIONS).
    Only Admins can register devices, edit configuration, delete, or reassign rooms.
    """
    message = 'Administrative credentials are required to modify device hardware configurations.'

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


class CanDispatchDeviceCommand(permissions.BasePermission):
    """
    Both Admin and authorized Staff can queue/issue device commands (e.g., relay toggle request),
    subject to channel safety lock validation.
    """
    message = 'Authorized institutional credentials required to issue device control commands.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_staff or user.is_superuser:
            return True

        profile = getattr(user, 'staff_profile', None)
        return bool(profile and profile.role in ['ADMIN', 'STAFF'])
