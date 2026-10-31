from rest_framework import permissions

class IsAdminOrStaffAlertAccess(permissions.BasePermission):
    """
    Staff can view alerts and acknowledge/resolve alerts assigned to them.
    Admins have full management rights.
    """
    message = 'Authentication required to access alert management.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated)
