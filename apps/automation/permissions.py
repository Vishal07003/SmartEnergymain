from rest_framework import permissions

class IsAdminOrStaffAutomationAccess(permissions.BasePermission):
    """
    Unified access: All authenticated users can view, create, edit, and evaluate automation rules.
    """
    message = 'Authentication required to access or manage automation rules.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class CanDispatchManualControl(permissions.BasePermission):
    """
    Unified access: All authenticated users can dispatch manual controls,
    strictly subject to channel safety-locks and real device online status.
    """
    message = 'Authentication required for manual device control.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
