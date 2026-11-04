from rest_framework import permissions

class IsAdminOrReadOnlyStaff(permissions.BasePermission):
    """
    Unified access: All authenticated users can view, create, update, and manage rooms and buildings.
    """
    message = 'Authentication required to access or modify room/building facilities.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
