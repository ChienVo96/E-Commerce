import json
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.db.models import (
    Prefetch,
    OuterRef,
    Subquery,
    Exists,
    Case,
    When,
    Value,
    Sum,
    Min,
    Max,
    CharField,
    IntegerField,
)
from django.db.models.functions import Coalesce
from .models import *
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import AccessMixin
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from django.utils.timezone import localtime, now


class StaffRequiredMixin(AccessMixin):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class SidebarStateAndPageActiveMixin:
    page_active = None
    subpage_active = None

    def get_sidebar_state(self):
        return self.request.COOKIES.get("sidebar", "")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_active"] = self.page_active
        context["subpage_active"] = self.subpage_active
        context["sidebar"] = self.get_sidebar_state()  # Lấy trạng thái từ cookie
        return context


class DashboardView(StaffRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        return render(request, "core/dashboard.html")


# ---------------------- CHAT ----------------------#
class ChatListView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, ListView):
    model = ChatRoom
    template_name = "core/chat_list.html"
    paginate_by = 6
    page_active = "chat"
    subpage_active = "chat_list"

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.order_by("-created_at")
        return queryset


class ChatDetailView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, DetailView):
    model = ChatRoom
    template_name = "core/chat_detail.html"
    context_object_name = "chat_room"
    page_active = "chat"
    subpage_active = "chat_detail"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Lấy danh sách tin nhắn và sắp xếp theo ngày
        messages = (
            self.object.messages.select_related("sender").all().order_by("created_at")
        )

        grouped_messages = {}
        for message in messages:
            # Convert thời gian tạo tin nhắn thành định dạng ngày (chỉ lấy phần ngày)
            message_date = localtime(message.created_at).date()
            if message_date not in grouped_messages:
                grouped_messages[message_date] = []
            grouped_messages[message_date].append(
                {
                    "content": message.content,
                    "sender": {"id": message.sender.id, "name": message.sender.name},
                    "time": message.created_at,
                }
            )
        context["messages_list"] = grouped_messages

        return context


# ---------------------- USER ----------------------#
class UserListView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, ListView):
    model = User
    template_name = "core/user_list.html"
    paginate_by = 6
    page_active = "user"
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = User.objects.all()
        if not self.request.user.is_superuser:
            queryset = User.objects.filter(is_staff=False,is_superuser=False)
        return queryset
    
# ---------------------- CATEGORY ----------------------#
class CategoryListView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, ListView):
    model = Category
    template_name = "core/category_list.html"
    paginate_by = 10
    page_active = "category"

    def get_queryset(self):
        queryset = super().get_queryset()

        # Sử dụng annotate để tính tổng số sản phẩm của danh mục cha và subcategories
        queryset = (
            queryset.filter(parent__isnull=True)
            .annotate(
                product_count=Count("products") + Count("subcategory__products"),
                subcategory_count=Count("subcategory"),
            )
            .order_by("-created_at", "-id")
        )

        return queryset


# ---------------------- PRODUCT ----------------------#
class ProductListView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, ListView):
    model = Product
    template_name = "core/product_list.html"
    page_active = "product"
    subpage_active = "product_list"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        return context

    def get_queryset(self):
        # Tính toán giá giảm cho từng variant của sản phẩm trong chương trình khuyến mãi
        variant_with_discount_price_queryset = Variant.objects.filter(
            product=OuterRef("products"),
        ).annotate(
            discount_price=Case(
                When(
                    promotion_items__promotion=OuterRef("pk"),  # Lọc đúng khuyến mãi hiện tại
                    promotion_items__discount_type="percent",  # Giảm giá theo phần trăm
                    then=F("price") * (1 - F("promotion_items__discount_value") / 100),
                ),
                When(
                    promotion_items__promotion=OuterRef("pk"),  # Lọc đúng khuyến mãi hiện tại
                    promotion_items__discount_type="amount",  # Giảm giá theo số tiền
                    then=F("price") - F("promotion_items__discount_value"),
                ),
                default=F("price"),  # Nếu không có giảm giá, lấy giá ban đầu
                output_field=IntegerField(),
            )
        ).values("discount_price")


        # Query Promotion với Subquery để tính min_price và max_price từ Variant của từng sản phẩm
        product_promotion_queryset = Promotion.objects.filter(
            end_date__gte=now(),  # Lọc chương trình khuyến mãi còn hiệu lực
        ).annotate(
            # Tính toán min_price cho từng sản phẩm trong chương trình khuyến mãi
            min_price=Subquery(
                variant_with_discount_price_queryset.order_by("discount_price")[:1].values("discount_price")
            ),
            # Tính toán max_price cho từng sản phẩm trong chương trình khuyến mãi
            max_price=Subquery(
                variant_with_discount_price_queryset.order_by("-discount_price")[:1].values("discount_price")
            ),
        ).distinct()
        
        queryset = (
            Product.objects.select_related("category")
            .prefetch_related(
                Prefetch(
                    "promotions", queryset=product_promotion_queryset)
            )
            .annotate(
                min_price_before_discount=Min("variants__price"),
                max_price_before_discount=Max("variants__price"),
                cover_image=Subquery(
                    Gallery.objects.filter(product=OuterRef("pk"))
                    .order_by("order")
                    .values("image")[:1],
                    output_field=CharField(),
                ),
                # Kiểm tra trạng thái kho hàng thấp hoặc hết hàng
                low_stock_status=Exists(
                    Variant.objects.filter(
                        product=OuterRef("pk"),
                        stock__lte=Coalesce(
                            F("stock_setting__safety_stock_threshold"), 0
                        ),
                        stock_setting__reminder_enabled=True,
                    )
                    | Variant.objects.filter(product=OuterRef("pk"), stock=0)
                ),
                variants_count=Count("variants"),
                total_stock=Sum("variants__stock"),
            )
            .order_by("-created_at", "-id")
        )

        return queryset


class ProductCreateUpdateView(
    StaffRequiredMixin, SidebarStateAndPageActiveMixin, TemplateView
):
    model = Product
    template_name = "core/product_create_update.html"
    page_active = "product"
    subpage_active = "product_create_update"

    def get(self, request, pk=None, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if pk:
            product = get_object_or_404(
                Product.objects.select_related("category")
                .prefetch_related(
                    Prefetch("gallery", queryset=Gallery.objects.order_by("order")),
                    Prefetch(
                        "attributes",
                        queryset=ProductAttribute.objects.prefetch_related(
                            "attribute_values"
                        ).order_by("id"),
                    ),
                    Prefetch(
                        "variants",
                        queryset=Variant.objects.prefetch_related(
                            "attribute_values__attribute"
                        ),
                    ),
                )
                .annotate(
                    attribute_count=Count("attributes"),
                    default_variant_id=Subquery(
                        Variant.objects.filter(
                            product=OuterRef("pk"), is_default=True
                        ).values("id")[:1]
                    ),
                ),
                pk=pk,
            )

            # Duyệt qua variants nhưng không tạo nhiều truy vấn
            variants_data = [
                {
                    "id": v.id,
                    "sku": v.sku if v.sku else "",
                    "price": float(v.price),
                    "stock": v.stock,
                    "is_default": v.is_default,
                    "attribute_values": {
                        av.attribute.name: av.value
                        for av in v.attribute_values.all()  # ✅ Không tạo nhiều truy vấn
                    },
                }
                for v in product.variants.all()
            ]

            context["variants_data"] = json.dumps(variants_data)
            context["product"] = product
        categories_with_subcategories = Category.objects.prefetch_related(
            Prefetch("subcategory", queryset=Category.objects.filter(is_active=True))
        ).filter(is_active=True, parent__isnull=True)
        context["categories"] = categories_with_subcategories
        return self.render_to_response(context)


# ---------------------- ORDER ----------------------#
class OrderListView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, ListView):
    model = Order
    template_name = "core/order_list.html"
    paginate_by = 10
    page_active = "order"
    subpage_active = "order_list"


class OrderDetailView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, DetailView):
    model = Order
    template_name = "core/order_detail.html"
    context_object_name = "order_room"
    page_active = "order"
    subpage_active = "order_detail"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context


class OrderCreateUpdateView(
    StaffRequiredMixin, SidebarStateAndPageActiveMixin, TemplateView
):
    model = Order
    template_name = "core/order_create_update.html"
    page_active = "order"
    subpage_active = "order_create_update"

    def get(self, request, pk=None, *args, **kwargs):

        context = self.get_context_data(**kwargs)
        if pk:
            order = get_object_or_404(
                Order.objects.prefetch_related(
                    Prefetch(
                        "items",
                        queryset=OrderItem.objects.order_by("-created_at", "-id"),
                    ),
                ),
                pk=pk,
            )
            context["order"] = order
        return self.render_to_response(context)


# ---------------------- Promotion ----------------------#
class PromotionListView(StaffRequiredMixin, SidebarStateAndPageActiveMixin, ListView):
    model = Promotion
    template_name = "core/promotion_list.html"
    paginate_by = 10
    page_active = "promotion"
    subpage_active = "promotion_list"
    ordering = ["-start_date"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Truy vấn danh sách chương trình khuyến mãi kèm số sản phẩm áp dụng và trạng thái
        queryset = queryset.annotate(
            product_count=Count("promotion_items__product", distinct=True),
            status=Case(
                When(start_date__gt=now(), then=Value("Sắp diễn ra")),
                When(end_date__lt=now(), then=Value("Đã kết thúc")),
                default=Value("Đang diễn ra"),
                output_field=models.CharField(),
            ),
        )
        return queryset


class PromotionCreateUpdateView(
    StaffRequiredMixin, SidebarStateAndPageActiveMixin, TemplateView
):
    template_name = "core/promotion_create_update.html"
    page_active = "promotion"
    subpage_active = "promotion_create_update"

    def get(self, request, pk=None, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if pk:
            promotion = get_object_or_404(
                Promotion.objects.prefetch_related(
                    Prefetch(
                        "promotion_items",
                        queryset=PromotionItem.objects.select_related(
                            "variant", "product"
                        ).order_by("-created_at", "-id"),
                    )
                ),
                pk=pk,
            )
            context["promotion"] = promotion
        context["categories"] = Category.objects.filter(is_active=True)
        return self.render_to_response(context)
