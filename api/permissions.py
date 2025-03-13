from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrStaff(BasePermission):
    owner_fields = ["user", "owner"]  # Mặc định

    def has_permission(self, request, view):
        # Đảm bảo user đã đăng nhập
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Kiểm tra quyền trên từng đối tượng"""
        # Nếu là staff hay admin, cho phép truy cập
        if request.user.is_staff or request.user.is_admin:
            return True

        # Lấy danh sách owner_fields từ View nếu có
        owner_fields = getattr(view, "owner_fields", self.owner_fields)

        # Kiểm tra quyền sở hữu dựa trên danh sách owner_fields
        for field in owner_fields:
            if hasattr(obj, field) and getattr(obj, field) == request.user:
                return True

        # Trường hợp obj chính là user (ví dụ model User)
        return obj == request.user


class IsStaff(BasePermission):
    """
    Chỉ cho phép người dùng có quyền staff truy cập.
    """

    def has_permission(self, request, view):
        # Kiểm tra xem người dùng đã đăng nhập và có quyền staff hay không
        return request.user.is_authenticated and request.user.is_staff


class IsStaffOrReadOnly(BasePermission):
    """
    Custom permission to only allow staff users to edit or delete objects.
    Read-only access is granted to all users.
    """

    def has_permission(self, request, view):
        # Read-only permissions are allowed for any request
        if request.method in SAFE_METHODS:
            return True

        # Write permissions are only allowed for staff users
        return request.user and request.user.is_staff
