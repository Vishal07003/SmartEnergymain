from rest_framework import permissions

class IsAdminUserRole(permissions.BasePermission):
    """
    Allows access only to users who have is_staff/is_superuser flag OR
    whose StaffProfile role is ADMIN.
    """
    message = 'You do not have administrative privileges to access this resource.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        if user.is_staff or user.is_superuser:
            return True
            
        profile = getattr(user, 'staff_profile', None)
        if profile and profile.role == 'ADMIN':
            return True
            
        return False


class IsStaffOrAdminUserRole(permissions.BasePermission):
    """
    Allows access to authenticated users who have either STAFF or ADMIN role.
    """
    message = 'Institutional staff or administrative credentials required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_staff or user.is_superuser:
            return True

        profile = getattr(user, 'staff_profile', None)
        return bool(profile and profile.role in ['STAFF', 'ADMIN'])

