from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')

class IsSuperAdminUser(permissions.BasePermission):
    """
    Allows access only to super admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)

class IsCoachUser(permissions.BasePermission):
    """
    Allows access only to coach users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'COACH')

class IsRegularUser(permissions.BasePermission):
    """
    Allows access only to regular users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'USER')

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    Assumes the model instance has an `user` attribute.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN' or request.user.is_superuser:
            return True
        
        # obj must have a user attribute or be a user object itself
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'username'):
            return obj == request.user
            
        return False
