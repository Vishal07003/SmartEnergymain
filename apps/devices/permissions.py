from rest_framework import permissions

class IsAdminOrReadOnlyStaffDevice(permissions.BasePermission):
    """
    Unified access: All authenticated users can view, register, edit, and assign devices.
    """
    message = 'Authentication required to manage campus devices.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class CanDispatchDeviceCommand(permissions.BasePermission):
    """
    All authenticated users can queue/issue device commands (e.g., relay toggle request),
    strictly subject to channel safety lock validation and device online status.
    """
    message = 'Authentication required to issue device control commands.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
