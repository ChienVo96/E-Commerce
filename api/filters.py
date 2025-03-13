import django_filters
from django.db.models import Count
from django_filters import rest_framework as filters
from core.models import Order, Product, Promotion, Variant, AttributeValue
from django.utils import timezone
from datetime import timezone as py_timezone

class BaseInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    """Cho phép lọc nhiều giá trị dưới dạng chuỗi
    Ví dụ: GET /products/?ids=1,2,3
    Filter sẽ tự động hiểu rằng lọc product có id 
    nằm trong danh sách [1, 2, 3]."""

    pass


class VariantFilter(django_filters.FilterSet):
    attr_value = django_filters.ModelMultipleChoiceFilter(
        queryset=AttributeValue.objects.all(),
        to_field_name="id",  # Lọc theo ID của AttributeValue
        method="filter_attr_value",
    )

    def filter_attr_value(self, queryset, name, value):
        attr_value_ids = [val.id for val in value]
        queryset = (
            queryset.filter(attribute_values__id__in=attr_value_ids)
            .annotate(num_attrs=Count("attribute_values"))
            .filter(num_attrs=len(attr_value_ids))
        )
        return queryset

    class Meta:
        model = Variant
        fields = ["product","attr_value"]


class ProductFilter(filters.FilterSet):
    ids = BaseInFilter(field_name="id", lookup_expr="in", label="IDs")
    category = BaseInFilter(
        field_name="category__id", lookup_expr="in", label="Danh Mục"
    )
    min_price = django_filters.NumberFilter(
        method="filter_min_price", label="Giá tối thiểu"
    )
    max_price = django_filters.NumberFilter(
        method="filter_max_price", label="Giá tối đa"
    )
    min_discount_price = django_filters.NumberFilter(
        method="filter_min_discount_price", label="Giá giảm tối thiểu"
    )
    max_discount_price = django_filters.NumberFilter(
        method="filter_max_price_discount", label="Giá giảm tối đa"
    )
    stock = django_filters.ChoiceFilter(
        method="filter_stock",
        choices=[
            ("in_stock", "Còn hàng"),
            ("out_of_stock", "Hết hàng"),
            ("all", "Tất cả"),
        ],
    )
    start_time = django_filters.DateTimeFilter(
        method="filter_time_overlap", label="Start Time"
    )
    end_time = django_filters.DateTimeFilter(
        method="filter_time_overlap", label="End Time"
    )

    def filter_min_price(self, queryset, name, value):
        """Lọc theo giá tối thiểu (dựa trên giá gốc nhỏ nhất của các biến thể)."""
        return queryset.filter(min_price__gte=value)

    def filter_max_price(self, queryset, name, value):
        """Lọc theo giá tối đa (dựa trên giá gốc lớn nhất của các biến thể)."""
        return queryset.filter(max_price__lte=value)
    
    def filter_min_price_discount(self, queryset, name, value):
        """Lọc theo giá tối thiểu (dựa trên giá giảm nhỏ nhất của sản phẩm)."""
        return queryset.filter(discount_price__gte=value)

    def filter_max_price_discount(self, queryset, name, value):
        """Lọc theo giá tối đa (dựa trên giá giảm nhỏ nhất của sản phẩm)."""
        return queryset.filter(discount_price__lte=value)

    def filter_stock(self, queryset, name, value):
        # """Lọc sản phẩm còn hàng hoặc hết hàng dựa vào tổng stock của tất cả variants."""
        # if value == "in_stock":
        #     return queryset.filter(total_stock__gt=0)  # Còn hàng
        # elif value == "out_of_stock":
        #     return queryset.filter(total_stock__lte=0)  # Hết hàng
        # return queryset

        """Lọc sản phẩm dựa vào stock của từng variant."""

        if value == "in_stock":
            return queryset.filter(
                variants__stock__gt=0
            )  # Có ít nhất một variant còn hàng
        elif value == "out_of_stock":
            return queryset.filter(variants__stock=0)  # Có ít nhất một variant hết hàng
        return queryset
    
    def filter_time_overlap(self, queryset, name, value):
        include_promotion = self.request.query_params.get("include_promotion", "false").strip().lower() in ["true", "1", "yes"]
        if not include_promotion:
            return Product.objects.none()
        """Lọc các Product không có chương trình khuyến mãi trùng thời gian"""
        if value:
            value = value.replace(tzinfo=None) if value.tzinfo is not None else value
            value = timezone.make_aware(value, timezone.get_current_timezone())
            value_utc = value.astimezone(py_timezone.utc)

            queryset = queryset.exclude(
                promotions__isnull=False,
                promotions__start_date__lt=value_utc,
                promotions__end_date__gt=value_utc,
            )
        return queryset
    
    class Meta:
        model = Product
        fields = ["is_active"]


class OrderFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(
        field_name="total_price", lookup_expr="gte", label="Giá tối thiểu"
    )
    max_price = django_filters.NumberFilter(
        field_name="total_price", lookup_expr="lte", label="Giá tối đa"
    )

    start_date = filters.DateFilter(
        field_name="created_at", lookup_expr="gte", label="Ngày bắt đầu"
    )
    end_date = filters.DateFilter(
        field_name="created_at", lookup_expr="lte", label="Ngày kết thúc"
    )

    payment_method = filters.ChoiceFilter(
        field_name="payment_method",
        choices=[
            ("cod", "COD"),
            ("bank_transfer", "Chuyển khoản"),
            ("e_wallet", "Ví điện tử"),
        ],
        label="Phương thức thanh toán",
    )

    customer_type = filters.ChoiceFilter(
        field_name="user__customer_profile__customer_type",
        choices=[("normal", "Thường"), ("vip", "VIP"), ("wholesale", "Đại lý")],
        label="Loại khách hàng",
    )

    shipping_status = filters.ChoiceFilter(
        field_name="shipping_status",
        choices=[
            ("pending", "Đang xử lý"),
            ("shipped", "Đang giao"),
            ("delivered", "Đã giao"),
            ("canceled", "Đã hủy"),
        ],
        label="Trạng thái giao hàng",
    )

    class Meta:
        model = Order
        fields = ["invoice", "user", "status"]


class PromotionFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            ("active", "Đang diễn ra"),
            ("upcoming", "Sắp diễn ra"),
            ("ended", "Đã kết thúc"),
        ],
        method="filter_status",
    )

    class Meta:
        model = Promotion
        fields = []

    def filter_status(self, queryset, name, value):
        """Lọc trạng thái chương trình khuyến mãi"""

        if value == "active":
            return queryset.filter(
                start_date__lte=now(), end_date__gte=now()
            )  # Đang diễn ra
        elif value == "upcoming":
            return queryset.filter(start_date__gt=now())  # Sắp diễn ra
        elif value == "ended":
            return queryset.filter(end_date__lt=now())  # Đã kết thúc
        return queryset


