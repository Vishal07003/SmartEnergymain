from rest_framework import permissions

class IsAdminUserRole(permissions.BasePermission):
    """
    Unified access: allows access to any authenticated, active user.
    """
    message = 'Authentication required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsStaffOrAdminUserRole(permissions.BasePermission):
    """
    Unified access: allows access to any authenticated, active user.
    """
    message = 'Authentication required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)

