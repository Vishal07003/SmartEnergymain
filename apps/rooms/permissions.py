from rest_framework import permissions

class IsAdminOrReadOnlyStaff(permissions.BasePermission):
    """
    Staff can view (safe methods: GET, HEAD, OPTIONS).
    Only Admins can perform create, update, delete (POST, PUT, PATCH, DELETE).
    """
    message = 'Administrative credentials are required to modify institutional room/building structures.'

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

