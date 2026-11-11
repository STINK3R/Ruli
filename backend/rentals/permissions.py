from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    message = "Аренда принадлежит другому пользователю."

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user_id == request.user.id
