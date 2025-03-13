import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from django.utils.timezone import now
from django.utils.translation import gettext as _, ngettext
from django.contrib.auth.tokens import default_token_generator
from django.db.models import (
    Count,
    Avg,
    F,
    Q,
    Case,
    When,
    Sum,
    Min,
    Max,
    Exists,
    OuterRef,
    Prefetch,
    Subquery,
    CharField,
    ExpressionWrapper,
    Value,
    DecimalField,
    IntegerField,
)
from django.db.models.functions import Coalesce, Concat
from django.core.cache import cache
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.generics import *
from rest_framework.mixins import *
from rest_framework.response import Response
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    AllowAny,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from urllib.parse import urlparse, parse_qs
from import_export.formats.base_formats import XLSX, XLS
from api.filters import (
    ProductFilter,
    PromotionFilter,
    VariantFilter,
)
from rest_framework.parsers import JSONParser
from api.pagination import *
from api.parsers import NestedMultiPartParser
from core.models import *
from .permissions import IsOwnerOrStaff, IsStaff, IsStaffOrReadOnly
from .serializers import *
from .resources import CategoryResource


@api_view(["GET"])
def get_districts(request, city_id):
    districts = District.objects.filter(city_id=city_id).values("id", "name")
    return Response(list(districts), status=status.HTTP_200_OK)


@api_view(["GET"])
def get_wards(request, district_id):
    wards = Ward.objects.filter(district_id=district_id).values("id", "name")
    return Response(list(wards), status=status.HTTP_200_OK)


# ---------------------- USER ---------------------- #
class UserListCreateAPIView(ListAPIView):
    serializer_class = UserSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    pagination_class = UserPagination
    filterset_fields = {
        "is_active": ["exact"],
    }
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at", "-id"]
    search_fields = ["email", "full_name", "phone_number", "address"]

    def get_permissions(self):
        """Cấp quyền cho các hành động GET và POST"""
        if self.request.method == "GET":
            # Chỉ cho phép staff truy cập danh sách người dùng
            return [IsStaff()]

        elif self.request.method == "POST":
            if self.request.user.is_authenticated and not self.request.user.is_staff:
                return Response(
                    {"message": "Bạn đã đăng nhập tài khoản."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return [
                AllowAny()
            ]  # Cho phép bất kỳ người dùng chưa đăng nhập hoặc staff tạo tài khoản mới.

        return super().get_permissions()

    def get_queryset(self):
        """Lọc danh sách người dùng dựa trên quyền"""
        queryset = User.objects.all()
        if not self.request.user.is_superuser:
            # Nếu người dùng không phải là admin
            queryset = queryset.filter(is_superuser=False, is_staff=False)

        return queryset

    def post(self, request, *args, **kwargs):
        """Lưu đối tượng người dùng mới nếu POST"""
        serializer = RegisterUserSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Tạo tài khoản thành công"),
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class UserRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer

    def get_permissions(self):
        """Cấp quyền cho các hành động GET, PUT, PATCH và DELETE"""
        if self.request.method in ["GET", "PUT", "PATCH"]:
            return [IsOwnerOrStaff()]

        if self.request.method == "DELETE":
            return [IsStaff()]

        return super().get_permissions()

    def get_queryset(self):
        """Lọc danh sách người dùng dựa trên quyền"""
        queryset = User.objects.all()

        if self.request.user.is_staff:
            # Nếu người dùng là staff, chỉ lấy khách hàng (không phải admin, không phải staff)
            queryset = queryset.filter(is_superuser=False, is_staff=False)

        return queryset

    def update(self, request, *args, **kwargs):
        """Chỉ thay đổi phần trả về mà không cần phải override toàn bộ phương thức update"""
        response = super().update(request, *args, **kwargs)

        # Thay đổi phần trả về (response) theo yêu cầu
        response.data = {
            "status": "success",
            "message": _("Cập nhật tài khoản thành công!"),
            "user": response.data,
        }
        return response


class BulkDeleteUserAPIView(APIView):
    permission_classes = [IsStaff]

    def delete(self, request, *args, **kwargs):
        """Xóa nhiều người dùng cùng lúc"""
        # Lấy danh sách user_id từ dữ liệu yêu cầu
        user_ids = request.data.get("user_ids", [])

        if not user_ids:
            return Response(
                {
                    "status": "error",
                    "message": _("Thiếu thông tin User Ids để xoá tài khoản."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        users = User.objects.filter(id__in=user_ids, is_superuser=False, is_staff=False)
        # Kiểm tra xem có phải tất cả user_ids là hợp lệ hay không
        invalid_user_ids = [
            user_id
            for user_id in user_ids
            if int(user_id) not in users.values_list("id", flat=True)
        ]
        if invalid_user_ids:
            return Response(
                {
                    "status": "error",
                    "message": _("Xoá không thành công do có tài khoản không hợp lệ."),
                    "user_ids": _("Tài khoản không hợp lệ : %s")
                    % ", ".join(map(str, invalid_user_ids)),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Nếu tất cả user_ids hợp lệ thì tiến hành xóa
        if users.exists():
            users.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Trường hợp không có người dùng nào để xóa
        return Response(
            {"status": "error", "message": _("Không tìm thấy người dùng nào để xóa.")},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PasswordChangeAPIView(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer
    queryset = User.objects.all()

    def get_object(self):
        """
        Lấy người dùng hiện tại (theo user đã đăng nhập).
        """
        return self.request.user

    def update(self, request, *args, **kwargs):
        """
        Thực hiện việc thay đổi mật khẩu.
        """
        # Gọi serializer để kiểm tra
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Cập nhật mật khẩu mới
        user = self.get_object()
        new_password = serializer.validated_data["new_password"]
        user.set_password(new_password)
        user.save()

        return Response(
            {"status": "success", "message": "Mật khẩu đã được thay đổi thành công."},
            status=status.HTTP_200_OK,
        )


class ForgetPasswordAPIView(GenericAPIView):
    serializer_class = ForgetPasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "message": "Không tìm thấy người dùng với email này.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tạo token reset mật khẩu
        token = default_token_generator.make_token(user)

        # Tạo liên kết để người dùng có thể đổi mật khẩu
        reset_link = (
            f"{settings.FRONTEND_URL}/reset-password/?token={token}&uid={user.pk}"
        )

        # Gửi email với liên kết reset mật khẩu
        send_mail(
            "Yêu cầu thay đổi mật khẩu",
            f"Vui lòng nhấp vào liên kết dưới đây để thay đổi mật khẩu của bạn: {reset_link}",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return Response(
            {
                "status": "success",
                "message": "Đã gửi email với hướng dẫn thay đổi mật khẩu.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetAPIView(APIView):
    serializer_class = PasswordResetSerializer

    def post(self, request, *args, **kwargs):
        # Lấy dữ liệu từ yêu cầu
        token = request.data.get("token")
        uid = request.data.get("uid")
        new_password = request.data.get("new_password")

        # Kiểm tra token và uid
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Người dùng không tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra token
        if not default_token_generator.check_token(user, token):
            return Response(
                {"status": "error", "message": "Mã xác nhận không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cập nhật mật khẩu mới cho người dùng
        user.set_password(new_password)
        user.save()

        return Response(
            {"status": "success", "message": "Mật khẩu đã được thay đổi thành công."},
            status=status.HTTP_200_OK,
        )


# -------------- SHIPPING ADDRESS ------------------ #
class ShippingAddressView(GenericAPIView):
    permission_classes = [IsOwnerOrStaff]
    serializer_class = ShippingAddressSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    queryset = UserShippingAddress.objects.all()

    def get(self, request, *args, **kwargs):
        """Lấy danh sách hoặc 1 địa chỉ cụ thể."""
        pk = kwargs.get("pk")
        if pk:
            address = get_object_or_404(UserShippingAddress, pk=pk)
            self.check_object_permissions(request, address)  # Kiểm tra quyền
            serializer = self.get_serializer(address)
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = self.filter_queryset(UserShippingAddress.objects.all())
        if not request.user.is_staff:
            queryset = queryset.filter(
                user=request.user
            )  # Người dùng chỉ xem địa chỉ của mình

        # page = self.paginate_queryset(queryset)
        # if page is not None:
        #     serializer = self.get_serializer(page, many=True)
        #     return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """Người dùng chỉ có thể tạo địa chỉ của chính mình."""
        data = request.data.copy()
        data["user"] = request.user.id  # Ép user là người tạo địa chỉ

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Địa chỉ giao hàng đã được thêm thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request, *args, **kwargs):
        """Chỉ chủ sở hữu hoặc staff mới có quyền cập nhật."""
        shipping_address = self.get_object()  # Lấy object theo quyền
        serializer = self.get_serializer(shipping_address, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Địa chỉ giao hàng đã được cập nhật thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, *args, **kwargs):
        """Chỉ chủ sở hữu hoặc staff mới có quyền cập nhật một phần."""
        shipping_address = self.get_object()
        serializer = self.get_serializer(
            shipping_address, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Cập nhật thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        """Chỉ chủ sở hữu hoặc staff mới có quyền xóa."""
        shipping_address = self.get_object()
        shipping_address.delete()
        return Response(
            {"status": "success", "message": _("Đã xoá thành công!")},
            status=status.HTTP_200_OK,
        )


# ------------- NOTIFICATION SETTING --------------- #
class NotificationSettingsView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    serializer_class = NotificationSettingsSerializer
    queryset = NotificationSettings.objects.all()
    filter_backends = [SearchFilter, DjangoFilterBackend]
    pagination_class = PageNumberPagination
    filterset_fields = {
        "user__email": ["icontains"],
        "user__phone_number": ["icontains"],
    }
    search_fields = ["user__email", "user__phone_number"]

    def get(self, request, *args, **kwargs):
        # Hoặc ta thêm ListModelMixin và return self.list(request, *args, **kwargs)
        # thay vì viết thủ công như bên dưới
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)  # Áp dụng phân trang
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(
                serializer.data
            )  # Trả về phản hồi phân trang

        # Trả về toàn bộ dữ liệu nếu không phân trang (fallback)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        notification_settings = self.get_object()
        serializer = self.get_serializer(
            instance=notification_settings, data=request.data
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Cài đặt thông báo đã được cập nhật thành công!"),
                }
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ------------------ NOTIFICATION ------------------ #
class NotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete_notification_count_key(self, notification_link):
        # Delete key cache trả lời bình luận liên quan đến notification
        parsed_url = urlparse(notification_link)
        query_params = parse_qs(parsed_url.query)
        # Lấy comment-id từ query parameters
        comment_id = query_params.get("comment-id", "")
        if comment_id:  # Chỉ xóa cache nếu comment_id tồn tại
            notification_count_key = f"notification_{self.request.user.id}_{comment_id}"
            cache.delete(notification_count_key)
        else:
            rating_id = query_params.get("rating-id", "")
            if rating_id:  # Chỉ xóa cache nếu rating_id tồn tại
                notification_count_key = (
                    f"notification_{self.request.user.id}_{rating_id}"
                )
                cache.delete(notification_count_key)

    def patch(self, request, pk=None, *args, **kwargs):
        if pk:
            # Đánh dấu một thông báo cụ thể là đã đọc
            try:
                notification = Notification.objects.get(pk=pk)
                notification_read, created = NotificationRead.objects.get_or_create(
                    user=request.user, notification=notification
                )
                notification_read.is_read = True
                notification_read.save()
                self.delete_notification_count_key(notification.link)
                next_url = notification.link if notification.link else ""
                return Response(
                    {
                        "message": "Thông báo đã được đánh dấu là đã đọc.",
                        "next_url": next_url,
                    },
                    status=200,
                )
            except Notification.DoesNotExist:
                return Response({"error": "Không tìm thấy thông báo."}, status=404)
        else:
            # Nếu không có ID, đánh dấu tất cả thông báo là đã đọc
            # unread_notifications = Notification.objects.filter(
            #     Q(user=request.user) | Q(notification_type__in=Notification.FILTER_TYPES)
            # ).exclude(
            #     notification_read__user=request.user,  # Loại bỏ thông báo đã có bản ghi trong NotificationRead
            #     notification_read__is_read=True  # Loại bỏ thông báo đã đọc
            # )

            unread_notifications = (
                Notification.objects.filter(
                    Q(user=request.user)
                    | Q(notification_type__in=Notification.FILTER_TYPES)
                )
                .annotate(
                    is_read=Exists(
                        NotificationRead.objects.filter(
                            user=request.user, notification=OuterRef("pk"), is_read=True
                        )
                    )
                )
                .filter(is_read=False)
            )

            # Cập nhật tất cả các thông báo còn lại là đã đọc, nếu chưa có bản ghi NotificationRead
            with transaction.atomic():
                # Tạo hoặc cập nhật các bản ghi NotificationRead
                notifications_to_update = []
                for notification in unread_notifications:
                    notification_read, created = NotificationRead.objects.get_or_create(
                        user=request.user, notification=notification
                    )
                    notification_read.is_read = True
                    notifications_to_update.append(notification_read)
                    self.delete_notification_count_key(notification.link)

                # Bulk update tất cả các bản ghi
                NotificationRead.objects.bulk_update(
                    notifications_to_update, ["is_read"]
                )

            return Response(
                {"message": "Tất cả thông báo được đánh dấu là đã đọc."}, status=200
            )


# -------------------- CATEGORY -------------------- #
class CategoryAPIView(mixins.ListModelMixin, GenericAPIView):
    permission_classes = [IsStaffOrReadOnly]
    serializer_class = CategorySerializer
    pagination_class = CategoryPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at"]
    search_fields = ["name"]

    def get_queryset(self):
        queryset = Category.objects.filter(parent__isnull=True).annotate(
            product_count=Count("products"), subcategory_count=Count("subcategory")
        )
        return queryset

    def get(self, request, *args, **kwargs):
        """Xử lý GET để lấy danh sách hoặc một danh mục cụ thể."""
        pk = kwargs.get("pk")
        if pk:
            category = self.get_object()
            serializer = self.get_serializer(category)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Xử lý POST để tạo mới danh mục và các subcategory."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Danh mục đã được thêm thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request, *args, **kwargs):
        """Xử lý PUT để cập nhật danh mục và các subcategory."""
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Danh mục cập nhật thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, *args, **kwargs):
        """Xử lý PATCH để cập nhật một phần danh mục."""
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Danh mục cập nhật thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        """Xử lý DELETE để xóa danh mục."""
        category = self.get_object()
        category.delete()
        return Response(
            {"status": "success", "message": _("Đã xoá thành công!")},
            status=status.HTTP_200_OK,
        )


class CategoryBulkDeleteView(APIView):
    permission_classes = [IsStaff]

    def delete(self, request, *args, **kwargs):
        """Xử lý DELETE để xóa nhiều danh mục cùng lúc."""
        category_ids = request.data.get(
            "ids", []
        )  # Lấy danh sách ID từ body của yêu cầu

        if not category_ids:
            return Response(
                {
                    "status": "error",
                    "message": _("Không có ID danh mục nào được cung cấp."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lọc các danh mục theo IDs
        categories_to_delete = Category.objects.filter(id__in=category_ids)

        if not categories_to_delete.exists():
            return Response(
                {
                    "status": "error",
                    "message": _("Không tìm thấy danh mục nào với các ID đã cung cấp."),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Xóa các danh mục
        deleted_count, deleted_count_detail = categories_to_delete.delete()
        category_deleted_count = deleted_count_detail.get("core.Category", 0)
        message = ngettext(
            "Đã xóa thành công %(count)s danh mục.",  # Dạng số ít
            "Đã xóa thành công %(count)s danh mục.",  # Dạng số nhiều
            category_deleted_count,
        ) % {"count": category_deleted_count}
        return Response(
            {"status": "success", "message": message}, status=status.HTTP_200_OK
        )


class CategoryImportView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"status": "error", "message": _("Không có file import.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if file is xlsx or xls
        if not file.name.endswith((".xlsx", ".xls")):
            return Response(
                {
                    "status": "error",
                    "message": _(
                        "File import không hợp lệ. File hợp lệ phải là .xlsx hoặc .xls"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Choose the correct format based on file extension
        format_class = XLSX() if file.name.endswith(".xlsx") else XLS()

        # Read the file content into a dataset
        dataset = format_class.create_dataset(file.read())

        # Use CategoryResource to import data
        category_resource = CategoryResource()
        result = category_resource.import_data(
            dataset, dry_run=True
        )  # Dry run for validation
        # Use CategoryResource to import data
        if result.has_errors():
            errors = {
                f"row_{index + 1}": error
                for index, error in enumerate(result.row_errors())
            }
            return Response(
                {
                    "status": "error",
                    "message": _("Import không thành công."),
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        category_resource.import_data(dataset, dry_run=False)
        return Response(
            {
                "status": "success",
                "message": _("%s danh mục đã nhập thành công.")
                % len(result.valid_rows()),
            },
            status=status.HTTP_200_OK,
        )


class CategoryExportView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        category_resource = CategoryResource()

        # Lấy danh sách ID danh mục từ request body
        category_ids = request.data.get("ids", [])

        # Bạn có thể lọc danh mục theo ID nếu cần
        if category_ids:
            categories = Category.objects.filter(id__in=category_ids)
            category_resource = (
                CategoryResource()
            )  # Tạo lại resource sau khi lọc dữ liệu

        # Xuất dữ liệu
        dataset = category_resource.export(queryset=categories)

        # Tạo phản hồi HTTP với tệp Excel (XLSX)
        response = HttpResponse(dataset.xlsx)
        response["Content-Disposition"] = "attachment; filename=categories.xlsx"

        return response


# -------------------- PRODUCT --------------------- #
class ProductAPIView(GenericAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProductCreateUpdateSerializer
    parser_classes = [JSONParser, NestedMultiPartParser]

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("category")
            .prefetch_related(
                "gallery",
                "attributes__attribute_values",
                Prefetch(
                    "variants",
                    queryset=Variant.objects.prefetch_related(
                        "attribute_values",
                    ).order_by("created_at", "id"),
                ),
            )
            .annotate(
                cover_image=Subquery(
                    Gallery.objects.filter(product=OuterRef("pk"))
                    .order_by()
                    .values("image")[:1]
                ),
            )
            .order_by("-created_at", "-id")
        )
        return queryset

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": "success", "product": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance=instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": "success", "product": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, *args, **kwargs):
        self.serializer_class = ProductVariantStockPriceUpdateSerializer
        instance = self.get_object()
        serializer = self.get_serializer(
            instance=instance, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": "success", "product": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductListAPIView(ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProductListSerializer
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at", "-id"]
    search_fields = ["sku", "name", "category__name"]

    def get_base_queryset(self):
        queryset = Product.objects.select_related("category").annotate(
            cover_image=Subquery(
                Gallery.objects.filter(product=OuterRef("pk"))
                .order_by("order")
                .values("image")[:1]
            ),
            total_stock=Sum("variants__stock"),
            min_price=Min("variants__price"),
            max_price=Max("variants__price"),
        )
        return queryset

    def get_queryset_include_variants(self):
        # Tính toán giá giảm cho từng variant của sản phẩm trong chương trình khuyến mãi
        variants_queryset = Variant.objects.prefetch_related("stock_setting").annotate(
            discount_price=Case(
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="percent",  # Giảm giá theo phần trăm
                    then=F("price") * (1 - F("promotion_items__discount_value") / 100),
                ),
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="amount",  # Giảm giá theo số tiền
                    then=F("price") - F("promotion_items__discount_value"),
                ),
                default=F("price"),  # Nếu không có giảm giá, lấy giá ban đầu
                output_field=IntegerField(),
            ),
            discount=Case(
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="amount",
                    then=ExpressionWrapper(
                        (F("promotion_items__discount_value") / F("price")) * 100,
                        output_field=IntegerField(),
                    ),
                ),
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="percent",
                    then=F("promotion_items__discount_value"),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
            discount_display=Case(
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="percent",
                    then=Concat(
                        F("promotion_items__discount_value"),
                        Value("%"),
                        output_field=CharField(),
                    ),
                ),
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="amount",
                    then=Concat(
                        F("promotion_items__discount_value"),
                        Value("₫"),
                        output_field=CharField(),
                    ),
                ),
                default=Value(None),
                output_field=CharField(),
            ),
            image=Subquery(
                AttributeValue.objects.filter(
                    Q(variants=OuterRef("pk")) & Q(image__isnull=False) & ~Q(image="")
                ).values("image")[:1]
            ),
        )

        queryset = self.get_base_queryset().prefetch_related(
            Prefetch("variants", queryset=variants_queryset)
        )
        return queryset

    def get_queryset_for_management(self):
        # Kiểm tra nếu có ít nhất một variant có stock ≤ safety_stock_threshold
        low_stock_queryset = Variant.objects.filter(
            Q(product=OuterRef("pk"))
            & (
                Q(
                    stock__lte=Coalesce(F("stock_setting__safety_stock_threshold"), 0),
                    stock_setting__reminder_enabled=True,
                )
                | Q(stock=0)
            )
        )

        # Tính toán giá giảm cho từng variant của sản phẩm trong chương trình khuyến mãi
        variant_with_discount_price_queryset = (
            Variant.objects.filter(
                product=OuterRef("products"),
            )
            .annotate(
                discount_price=Case(
                    When(
                        promotion_items__promotion=OuterRef(
                            "pk"
                        ),  # Lọc đúng khuyến mãi hiện tại
                        promotion_items__discount_type="percent",  # Giảm giá theo phần trăm
                        then=F("price")
                        * (1 - F("promotion_items__discount_value") / 100),
                    ),
                    When(
                        promotion_items__promotion=OuterRef(
                            "pk"
                        ),  # Lọc đúng khuyến mãi hiện tại
                        promotion_items__discount_type="amount",  # Giảm giá theo số tiền
                        then=F("price") - F("promotion_items__discount_value"),
                    ),
                    default=F("price"),  # Nếu không có giảm giá, lấy giá ban đầu
                    output_field=IntegerField(),
                )
            )
            .values("discount_price")
        )

        # Tính min_price và max_price cho mỗi chương trình khuyến mãi của sản phẩm
        product_promotion_queryset = (
            Promotion.objects.filter(
                end_date__gt=now(),  # Lọc chương trình khuyến mãi còn hiệu lực
            )
            .annotate(
                # Tính toán min_price cho từng sản phẩm trong chương trình khuyến mãi
                min_price=Subquery(
                    variant_with_discount_price_queryset.order_by("discount_price")[
                        :1
                    ].values("discount_price")
                ),
                # Tính toán max_price cho từng sản phẩm trong chương trình khuyến mãi
                max_price=Subquery(
                    variant_with_discount_price_queryset.order_by("-discount_price")[
                        :1
                    ].values("discount_price")
                ),
            )
            .distinct()
        )

        queryset = (
            self.get_base_queryset()
            .annotate(
                variants_count=Count("variants"),
                low_stock_status=Exists(low_stock_queryset),
            )
            .prefetch_related(
                Prefetch("promotions", queryset=product_promotion_queryset),
            )
        )

        return queryset

    def get_queryset_include_promotion(self):
        queryset = self.get_base_queryset().prefetch_related("promotions")
        self.pagination_class = None
        return queryset

    def get_queryset(self):
        queryset = self.get_base_queryset()

        # Lấy params
        include_variants = self.request.query_params.get("include_variants", "false").strip().lower() in ["true", "1", "yes"]
        include_promotion = self.request.query_params.get("include_promotion", "false").strip().lower() in ["true", "1", "yes"]
        management = self.request.query_params.get("management", "false").strip().lower() in ["true", "1", "yes"]
        
        if include_variants:
            queryset = self.get_queryset_include_variants()
        elif include_promotion:
            queryset = self.get_queryset_include_promotion()
        elif management:
            queryset = self.get_queryset_for_management()
        return queryset


class ProductListPublicAPIView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListPublicSerializer
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at", "-id"]
    search_fields = ["sku", "name", "category__name"]

    def get_queryset(self):
        best_price_discount_variant = (
            Variant.objects.filter(product=OuterRef("pk"))
            .annotate(
                discount_price=Case(
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="percent",
                        then=ExpressionWrapper(
                            F("price")
                            * (1 - F("promotion_items__discount_value") / 100),
                            output_field=DecimalField(max_digits=10, decimal_places=0),
                        ),
                    ),
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="amount",
                        then=ExpressionWrapper(
                            F("price") - F("promotion_items__discount_value"),
                            output_field=DecimalField(max_digits=10, decimal_places=0),
                        ),
                    ),
                    default=F("price"),
                    output_field=DecimalField(max_digits=10, decimal_places=0),
                ),
                discount=Case(
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="amount",
                        then=ExpressionWrapper(
                            (F("promotion_items__discount_value") / F("price")) * 100,
                            output_field=IntegerField(),
                        ),
                    ),
                    When(
                        promotion_items__discount_type="percent",
                        then=F("promotion_items__discount_value"),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )
            .order_by("discount_price")[:1]
        )
        queryset = Product.objects.select_related("category").annotate(
            cover_image=Subquery(
                Gallery.objects.filter(product=OuterRef("pk"))
                .order_by("order")
                .values("image")[:1]
            ),
            rating_star=Avg("reviews__score"),
            variant_id=Subquery(best_price_discount_variant.values("id")),
            price=Subquery(best_price_discount_variant.values("price")),
            discount_price=Subquery(
                best_price_discount_variant.values("discount_price")
            ),
            discount=Subquery(best_price_discount_variant.values("discount")),
        )
        return queryset


class ProductBulkDeleteAPIView(APIView):
    permission_classes = [IsStaff]

    def delete(self, request, *args, **kwargs):
        """Xử lý DELETE để xóa nhiều sản phẩm cùng lúc."""
        ids = request.data.get("ids", [])  # Lấy danh sách ID từ body của yêu cầu

        if not ids:
            return Response(
                {
                    "status": "success",
                },
                status=status.HTTP_200_OK,
            )

        # Chuyển tất cả ids từ string sang integer
        try:
            ids = set(map(int, ids))
        except ValueError:
            return Response(
                {"status": "error", "message": _("Danh sách IDs không hợp lệ.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lọc các sản phẩm theo IDs
        products_to_delete = Product.objects.filter(id__in=ids)
        found_ids = set(products_to_delete.values_list("id", flat=True))

        # Kiểm tra xem có ID nào không tồn tại không
        missing_ids = ids - found_ids
        if missing_ids:
            return Response(
                {
                    "status": "error",
                    "message": _("Một số ID không hợp lệ hoặc không tồn tại."),
                    "missing_ids": list(missing_ids),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Xóa các sản phẩm
        deleted_count, deleted_details = products_to_delete.delete()
        # deleted_count tổng các bản ghi bị xoá
        # Nếu sản phẩm bị xoá có các quan hệ ForeignKey
        # với các model khác và có on_delete=models.CASCADE
        # thì Django sẽ xóa luôn các bản ghi liên quan
        product_deleted_count = deleted_details.get("core.Product", 0)
        message = ngettext(
            "Đã xoá thành công %(count)s sản phẩm.",
            "Đã xoá thành công %(count)s sản phẩm.",
            product_deleted_count,
        ) % {"count": product_deleted_count}

        return Response(
            {"status": "success", "message": message}, status=status.HTTP_200_OK
        )


class ProductReviewAPIView(mixins.ListModelMixin, GenericAPIView):
    """
    API để lấy danh sách đánh giá và thêm đánh giá mới.

    - `GET /products/{id}/reviews/` → Lấy danh sách đánh giá.
    - `POST /products/{id}/reviews/` → Thêm đánh giá mới.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ReviewPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["score"]
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        """Lấy danh sách đánh giá theo sản phẩm."""
        return Review.objects.filter(product_id=self.kwargs.get("pk")).select_related(
            "comment", "user"
        )

    def get(self, request, *args, **kwargs):
        """Trả về danh sách đánh giá."""
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Thêm một đánh giá mới."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Đánh giá đã được thêm thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ProductReviewSummaryAPIView(APIView):
    """
    API để lấy tổng quan đánh giá của sản phẩm.

    - `GET /products/{id}/reviews/summary/` → Lấy tổng quan đánh giá.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        """Trả về thống kê chi tiết đánh giá của sản phẩm."""
        product = get_object_or_404(Product, pk=pk)
        ratings = Review.objects.filter(product=product).aggregate(
            score_avg=Avg("score"),
            total_ratings=Count("score"),
            rating_1=Count(Case(When(score=1, then=1))),
            rating_2=Count(Case(When(score=2, then=1))),
            rating_3=Count(Case(When(score=3, then=1))),
            rating_4=Count(Case(When(score=4, then=1))),
            rating_5=Count(Case(When(score=5, then=1))),
        )

        return Response(
            {
                "product_id": product.id,
                "average_score": (
                    round(ratings["score_avg"], 1) if ratings["score_avg"] else 0
                ),
                "total_ratings": ratings["total_ratings"],
                "ratings_distribution": {
                    "5": ratings["rating_5"],
                    "4": ratings["rating_4"],
                    "3": ratings["rating_3"],
                    "2": ratings["rating_2"],
                    "1": ratings["rating_1"],
                },
            },
            status=status.HTTP_200_OK,
        )


class ProductCommentAPIView(mixins.ListModelMixin, GenericAPIView):
    """
    Lấy danh sách bình luận
    Thêm bình luận mới cho sản phẩm.
    """

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    pagination_class = CommentPagination
    filterset_fields = ["product", "user"]
    ordering_fields = ["updated_at"]

    def get_queryset(self):
        """Trả về danh sách bình luận không liên quan đến đánh giá (rating)."""
        queryset = Comment.objects.filter(review__isnull=True).prefetch_related(
            "replies"
        )
        product_id = self.kwargs.get("pk")
        if product_id:
            queryset = queryset.filter(
                product_id=product_id, parent__isnull=True
            ).select_related("user")
        return queryset

    def get(self, request, *args, **kwargs):
        """Lấy danh sách bình luận theo sản phẩm."""
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Thêm bình luận mới cho sản phẩm."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Phản hồi đã được thêm thành công!"),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


# -------------------- VARIANT --------------------- #
class VariantListAPIView(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = VariantSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = VariantFilter

    def get_queryset(self):
        queryset = Variant.objects.annotate(
            discount_price=Case(
                When(
                    promotion_items__discount_type="amount",
                    then=F("price") - F("promotion_items__discount_value"),
                ),
                When(
                    promotion_items__discount_type="percent",
                    then=F("price") * (1 - F("promotion_items__discount_value") / 100),
                ),
                default=F("price"),
                output_field=DecimalField(),
            ),
            discount=Case(
                When(
                    promotion_items__discount_type="amount",
                    then=ExpressionWrapper(
                        (F("promotion_items__discount_value") / F("price")) * 100,
                        output_field=FloatField(),
                    ),
                ),
                When(
                    promotion_items__discount_type="percent",
                    then=F("promotion_items__discount_value"),
                ),
                default=Value(0),
                output_field=FloatField(),
            ),
        )
        return queryset


# ------------------- PROMOTION -------------------- #
class PromotionAPIView(
    GenericAPIView,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.RetrieveModelMixin,
):
    serializer_class = PromotionSerializer
    pagination_class = PromotionPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filter_class = PromotionFilter
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at"]
    search_fields = ["name"]

    def get_queryset(self):
        queryset = Promotion.objects.prefetch_related(
            Prefetch(
                "promotion_items",
                queryset=PromotionItem.objects.select_related("product", "variant"),
            )
        ).all()
        return queryset

    def get(self, request, pk=None, *args, **kwargs):
        """Lấy danh sách các chương trình khuyến mãi
        Nếu có pk thì lấy chi tiết chương trình khuyến mãi đó"""
        if pk:
            return self.retrieve(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Tạo mới một chương trình khuyến mãi"""
        response = self.create(request, *args, **kwargs)
        response.data = {
            "status": "success",
            "message": _("Chương trình khuyến mãi đã được tạo thành công."),
            "promotion": response.data,
        }
        return response

    def put(self, request, *args, **kwargs):
        """Cập nhật thông tin một chương trình khuyến mãi"""
        response = self.update(request, *args, **kwargs)
        response.data = {
            "status": "success",
            "message": _("Chương trình khuyến mãi cập nhật thành công."),
            "promotion": response.data,
        }
        return response

    def delete(self, request, *args, **kwargs):
        """Xóa một chương trình khuyến mãi"""
        # HTTP 204 No Content nên không kèm data gửi về
        # nếu muốn thêm thông báo thì đổi thành 200 hoặc 202
        return self.destroy(request, *args, **kwargs)


# --------------------- CART ----------------------- #
class CartView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def get_queryset(self):

        user = self.request.user

        variant_queryset = Variant.objects.annotate(
            image=Subquery(
                AttributeValue.objects.filter(
                    Q(variants=OuterRef("pk")) & Q(image__isnull=False) & ~Q(image="")
                ).values("image")[:1]
            ),
            discount_price=Case(
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="percent",
                    then=ExpressionWrapper(
                        F("price") * (1 - F("promotion_items__discount_value") / 100),
                        output_field=DecimalField(max_digits=10, decimal_places=0),
                    ),
                ),
                When(
                    promotion_items__promotion__start_date__lte=now(),
                    promotion_items__promotion__end_date__gt=now(),
                    promotion_items__discount_type="amount",
                    then=ExpressionWrapper(
                        F("price") - F("promotion_items__discount_value"),
                        output_field=DecimalField(max_digits=10, decimal_places=0),
                    ),
                ),
                default=F("price"),
                output_field=DecimalField(max_digits=10, decimal_places=0),
            ),
            discount=Case(
                When(
                    promotion_items__discount_type="percent",
                    then=F("promotion_items__discount_value"),
                ),
                When(
                    promotion_items__discount_type="amount",
                    then=(F("promotion_items__discount_value") / F("price")) * 100,
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )

        product_queryset = Product.objects.annotate(
            cover_image=Subquery(
                Gallery.objects.filter(product=OuterRef("id"))
                .order_by("order")
                .values("image")[:1]  # Lấy ảnh đại diện đầu tiên
            )
        )
        # Query giỏ hàng của user
        cart_queryset = (
            Cart.objects.filter(user=user)
            .prefetch_related(
                Prefetch(
                    "cart_items",
                    queryset=CartItem.objects.prefetch_related(
                        Prefetch("product", queryset=product_queryset),
                        Prefetch(
                            "variant", queryset=variant_queryset
                        ),  # Gộp luôn variant với giá, ảnh, stock
                    ),
                )
            )
            .annotate(
                total_items=Count("cart_items"),
            )
            .first()
        )

        return cart_queryset

    def get(self, request, *args, **kwargs):
        cart = self.get_queryset().first()
        if not cart:
            return Response({"message": "Giỏ hàng trống."}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemView(GenericAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    owner_fields = ["cart__user"]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": "success", "message": _("Đã thêm sản phẩm vào giỏ hàng")},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "status": "success",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk, *args, **kwargs):
        user = self.request.user
        cart_item = CartItem.objects.filter(id=pk, cart__user=user)
        if not cart_item.exists():
            return Response(
                status=status.HTTP_404_NOT_FOUND,
            )
        cart_item.first().delete()
        return Response(
            {
                "status": "success",
            },
            status=status.HTTP_200_OK,
        )


# --------------------- ORDER ---------------------- #
class PlaceOrderView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        cart = get_object_or_404(Cart, user=user)

        # Kiểm tra giỏ hàng có sản phẩm không
        if not cart.cart_items.exists():
            return Response(
                {"status": "error", "message": _("Giỏ hàng của bạn trống.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            data = request.data.copy()  # Sao chép dữ liệu request
            shipping_address_data = data.get("shipping_address")
            shipping_address_id = shipping_address_data.get("id")

            # Lấy đầy đủ thông tin địa chỉ từ ID
            if shipping_address_id:
                shipping_address = get_object_or_404(
                    UserShippingAddress, id=shipping_address_id, user=user
                )
                shipping_address_data = ShippingAddressSerializer(shipping_address).data

            cart_items = CartItem.objects.filter(cart=cart).values(
                "product_id", "variant_id", "quantity"
            )
            # Chuẩn bị dữ liệu order
            order_data = {
                "user": user.id,
                "shipping_address": shipping_address_data,  # Gán đầy đủ thông tin địa chỉ
                "items": cart_items,
                "payment": {
                    "user": user.id,
                    "payment_method": data.get("payment_method"),
                },  # Giữ nguyên payment từ request
                "shipping_cost": 30000,  # Giả sử phí ship cố định
            }
            order_serializer = self.get_serializer(data=order_data)

            if order_serializer.is_valid():
                order = order_serializer.save()

                # Xóa giỏ hàng sau khi đặt hàng
                cart.cart_items.all().delete()

                return Response(
                    {
                        "success": True,
                        "order": order_serializer.data,
                        "next_url": reverse(
                            "store:order_detail", kwargs={"invoice": order.invoice}
                        ),
                    },
                    status=status.HTTP_201_CREATED,
                )
            return Response(
                {
                    "status": "error",
                    "message": _("Không thể tạo đơn hàng."),
                    "errors": order_serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


# ------------------- WISHLIST --------------------- #
class WishlistAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Wishlist.objects.filter(user=self.request.user)
        return queryset

    def post(self, request):
        product_id = request.data.get("product_id")
        variant_id = request.data.get("variant_id")

        if not product_id or not variant_id:
            return Response(
                {"status": "error", "message": _("Product not found.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kiểm tra xem sản phẩm có trong wishlist không
        wishlist, created = Wishlist.objects.get_or_create(
            user=request.user,
            product_id=product_id,
            variant_id=variant_id,
        )

        if not created:
            return Response(
                {
                    "status": "success",
                    "message": _("Sản phẩm đã có trong danh sách yêu thích của bạn."),
                },
                status=status.HTTP_200_OK,
            )

        # Trả về số lượng wishlist
        wishlist_count = request.user.wishlist.count()
        return Response(
            {
                "status": "success",
                "message": _("Đã thêm sản phẩm vào danh sách yêu thích của bạn."),
                "data": {
                    "wishlist_count": wishlist_count,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, pk=None):
        wishlist = None
        if pk:
            wishlist = self.get_object()
        else:
            product_id = request.data.get("product_id")
            variant_id = request.data.get("variant_id")
            if not product_id or not variant_id:
                return Response(
                    {
                        "status": "error",
                        "message": _(
                            "Không tìm thấy sản phẩm trong danh sách yêu thích."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Kiểm tra xem sản phẩm có trong wishlist không
            wishlist = Wishlist.objects.filter(
                user=request.user,
                product_id=product_id,
                variant_id=variant_id,
            ).first()
        if wishlist:
            wishlist.delete()
        # Trả về số lượng wishlist hiện tại
        wishlist_count = request.user.wishlist.count()
        return Response(
            {
                "status": "success",
                "message": _("Đã xoá sản phẩm khỏi danh sách yêu thích của bạn."),
                "data": {
                    "wishlist_count": wishlist_count,
                },
            },
            status=status.HTTP_200_OK,
        )


# --------------------- CHAT ----------------------- #
class ChatUserAPIView(APIView):
    """
    API View để tạo người dùng chat mới.
    """

    permission_classes = [
        AllowAny,
    ]

    def post(self, request, *args, **kwargs):
        # Lấy dữ liệu từ request
        serializer = ChatUserSerializer(data=request.data)

        if serializer.is_valid():
            # Lưu người dùng vào cơ sở dữ liệu
            chat_user = serializer.save()
            # Tạo guest_id nếu không có
            guest_id = (
                chat_user.guest_id if chat_user.guest_id else get_random_string(16)
            )

            # Trả về response và set guest_id vào cookie
            response = Response(
                {"status": "success", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )

            # Thiết lập cookie guest_id
            response.set_cookie(
                key="guestid",  # Tên cookie
                value=guest_id,  # Giá trị của cookie (guest_id)
                httponly=True,  # Chỉ có thể truy cập từ server, không thể truy cập từ JavaScript
                samesite="Lax",  # Bảo vệ CSRF
                max_age=60 * 60 * 24,  # Thời gian sống của cookie (1 ngày)
            )

            return response

        # Trả về lỗi nếu dữ liệu không hợp lệ
        return Response(
            {
                "status": "error",
                "message": "Dữ liệu không hợp lệ!",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ChatRoomAPIView(GenericAPIView):
    """
    API View để tạo người dùng chat mới.
    """

    permission_classes = [
        AllowAny,
    ]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.all()

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Tạo phòng chat thành công."),
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {
                "status": "error",
                "error": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, *args, **kwargs):
        self.permission_classes = [IsStaff]
        self.check_permissions(request)
        chat_room = self.get_object()
        old_status = chat_room.status
        serializer = self.serializer_class(
            data=request.data, instance=chat_room, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": _("Cập nhật phòng chat thành công."),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "status": "error",
                "error": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        self.permission_classes = [IsStaff]
        self.check_permissions(request)
        chat_room = self.get_object()
        # Lấy dữ liệu từ request
        if chat_room:
            chat_room.delete()
            return Response(
                {"status": "success", "message": _("Xoá phòng chat thành công.")},
                status=status.HTTP_200_OK,
            )
