from rest_framework import permissions

class IsAdminOrStaffAutomationAccess(permissions.BasePermission):
    """
    Staff can view rules, command logs, and execute permitted manual controls.
    Only Admins can create, edit, or delete automation rules.
    """
    message = 'Administrative credentials are required to modify automation rules.'

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


class CanDispatchManualControl(permissions.BasePermission):
    """
    Authenticated staff and administrators can dispatch manual controls subject to safety lock validation.
    """
    message = 'Institutional staff or administrative credentials required for manual device control.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated)
