from decimal import Decimal
from django.db.models import F, Sum, Min, Max
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.utils.formats import number_format
from core.models import default_no_image
from itertools import product as itertools_product
from django.core.files.base import ContentFile
from core.models import *


class TokenObtainSerializer(serializers.ModelSerializer):
    username = (
        serializers.CharField()
    )  # Sử dụng trường username (có thể là email hoặc số điện thoại)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        # Tìm kiếm người dùng theo email hoặc số điện thoại
        user = User.objects.filter(email=username).first()
        if user is None:
            user = User.objects.filter(phone_number=username).first()
        if user is None:
            raise serializers.ValidationError("User not found.")

        # Kiểm tra mật khẩu
        if not user.check_password(password):
            raise serializers.ValidationError("Invalid password.")

        # Kiểm tra xem tài khoản có đang active hay không
        if not user.is_active:
            raise serializers.ValidationError("User account is inactive.")

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "avatar",
            "full_name",
            "email",
            "phone_number",
            "birth",
            "gender",
            "address",
            "is_active",
        ]

    def update(self, instance, validated_data):
        """
        Cập nhật thông tin người dùng.
        """
        # Cập nhật các trường không liên quan đến mật khẩu
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RegisterUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "avatar",
            "full_name",
            "email",
            "phone_number",
            "password",
            "confirm_password",
            "is_active",
        ]

    def validate(self, data):
        """
        Kiểm tra mật khẩu và xác nhận mật khẩu có khớp không (chỉ khi tạo mới).
        """
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Mật khẩu không khớp"}
            )

        # Loại bỏ confirm_password sau khi kiểm tra tính hợp lệ
        data.pop("confirm_password")

        # Kiểm tra nếu người dùng không phải staff thì không cho phép sửa is_active
        user = self.context.get("request").user  # Lấy người dùng từ context
        if user and not user.is_staff:
            data.pop(
                "is_active", None
            )  # Loại bỏ 'is_active' nếu người dùng không phải là staff

        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        """
        Kiểm tra tính hợp lệ của mật khẩu cũ và mật khẩu mới.
        """
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        confirm_new_password = data.get("confirm_new_password")

        user = self.context.get("user")

        # Kiểm tra mật khẩu cũ
        if not user.check_password(old_password):
            raise ValidationError({"old_password": _("Mật khẩu cũ không chính xác.")})

        # Kiểm tra mật khẩu mới và xác nhận mật khẩu
        if new_password != confirm_new_password:
            raise ValidationError(
                {"confirm_new_password": _("Mật khẩu mới không khớp.")}
            )

        return data


class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": _("Mật khẩu không khớp.")}
            )
        return data


class ShippingAddressSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = UserShippingAddress
        fields = [
            "id",
            "user",
            "full_name",
            "phone_number",
            "street_address",
            "city",
            "district",
            "ward",
            "postal_code",
            "is_default",
        ]

    def to_representation(self, instance):
        """Trả về city, district, ward dưới dạng {id, name}"""
        data = super().to_representation(instance)
        data["city"] = self.get_related_field_data(instance.city)
        data["district"] = self.get_related_field_data(instance.district)
        data["ward"] = self.get_related_field_data(instance.ward)
        return data

    def get_related_field_data(self, instance):
        """Trả về dữ liệu {id, name} của city, district, ward"""
        if instance:
            return {"id": instance.id, "name": instance.name}
        return None

    def to_internal_value(self, data):
        """Chỉ nhận ID của city, district, ward khi gửi request"""
        data = data.copy()
        if isinstance(data.get("city"), dict):
            data["city"] = data["city"].get("id")
        if isinstance(data.get("district"), dict):
            data["district"] = data["district"].get("id")
        if isinstance(data.get("ward"), dict):
            data["ward"] = data["ward"].get("id")
        return super().to_internal_value(data)


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = [
            "email_notification",
            "sms_notification",
            "promotion_email",
            "promotion_sms",
        ]


class SubcategorySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    subcategory = SubcategorySerializer(many=True, required=False)
    image = serializers.ImageField(
        required=False, max_length=None, allow_empty_file=True
    )
    product_count = serializers.IntegerField(read_only=True)
    subcategory_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "image",
            "name",
            "slug",
            "is_active",
            "subcategory",
            "subcategory_count",
            "product_count",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "slug": {"read_only": True},
        }

    def validate_subcategory_data(self, subcategories_data):
        """
        Kiểm tra subcategory trong cùng một category.
        """
        seen_names = set()
        errors = []
        for subcategory in subcategories_data:
            subcategory_name = subcategory.get("name", "").strip().lower()

            # Kiểm tra trùng lặp tên
            if subcategory_name in seen_names:
                errors.append(
                    {"name": _('Tên phân loại phụ "%s" bị trùng.' % subcategory_name)}
                )
            else:
                errors.append({})
            seen_names.add(subcategory_name)
        if any(errors):
            raise serializers.ValidationError(
                {"status": "error", "error": {"subcategory": errors}}
            )

    def create(self, validated_data):
        subcategories_data = validated_data.pop("subcategory", [])

        # Gọi validate subcategory
        self.validate_subcategory_data(subcategories_data)

        with transaction.atomic():
            category = super().create(validated_data)
            for subcategory_data in subcategories_data:
                Category.objects.create(parent=category, **subcategory_data)
            return category

    def update(self, instance, validated_data):
        subcategories_data = validated_data.pop("subcategory", [])
        # Gọi validate subcategory
        self.validate_subcategory_data(subcategories_data)

        with transaction.atomic():
            category = super().update(instance, validated_data)

            subcategories_dict = {
                sub["id"]: sub for sub in subcategories_data if "id" in sub
            }
            keep_subcategory_ids = set(subcategories_dict.keys())

            # Duyệt qua subcategories hiện có và cập nhật hoặc xóa nếu không có trong danh sách
            for subcategory in category.subcategory.all():
                if subcategory.id in keep_subcategory_ids:
                    subcategory_data = subcategories_dict[subcategory.id]
                    for key, value in subcategory_data.items():
                        setattr(subcategory, key, value)  # Gán giá trị mới
                    subcategory.parent = category  # Đảm bảo parent cập nhật đúng
                    subcategory.save()  # Lưu thay đổi vào DB
                else:
                    # Xóa subcategory nếu không có trong danh sách cập nhật
                    subcategory.delete()

            # Tạo mới subcategories không có ID
            for subcategory_data in subcategories_data:
                if "id" not in subcategory_data:  # Nếu không có ID, nghĩa là mới
                    subcategory_data["parent"] = category
                    Category.objects.create(**subcategory_data)

            return category


class GallerySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    order = serializers.IntegerField(required=False)

    class Meta:
        model = Gallery
        fields = ["id", "image", "order"]


class StockSettingSerializer(serializers.ModelSerializer):
    safety_stock_threshold = serializers.IntegerField(
        min_value=0,
        error_messages={
            "min_value": _("Hạn mức phải lớn hơn hoặc bằng 0."),
            "invalid": _("Hạn mức phải là một số nguyên."),
            "null": _("Hạn mức không được để trống."),
        },
    )
    reminder_enabled = serializers.BooleanField(required=False, default=False)
    low_stock_status = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockSetting
        fields = [
            "id",
            "safety_stock_threshold",
            "reminder_enabled",
            "low_stock_status",
        ]


class PromotionItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = PromotionItem
        fields = ["id", "product", "variant", "discount_type", "discount_value"]

    def validate(self, attrs):
        product = attrs.get("product")
        variant = attrs.get("variant")
        discount_type = attrs.get("discount_type")
        discount_value = attrs.get("discount_value")

        if product and variant and variant.product != product:
            raise serializers.ValidationError(
                {"variant": _("Variant không thuộc sản phẩm đã chọn.")}
            )

        if discount_value is not None:
            if discount_type == "amount" and discount_value <= 0:
                raise serializers.ValidationError(
                    {"discount_value": _("Giá trị giảm giá phải lớn hơn 0.")}
                )
            elif discount_type == "percent" and not (0 < discount_value <= 100):
                raise serializers.ValidationError(
                    {"discount_value": _("Giá trị giảm giá phải trong khoảng 1-100%.")}
                )

        return attrs


class PromotionSerializer(serializers.ModelSerializer):
    promotion_items = PromotionItemSerializer(many=True, required=False)

    class Meta:
        model = Promotion
        fields = ["id", "name", "start_date", "end_date", "promotion_items"]

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"start_date": _("Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc.")}
            )

        if end_date and end_date < now():
            raise serializers.ValidationError(
                {"end_date": _("Thời gian kết thúc phải lớn hơn thời gian hiện tại.")}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        promotion_items_data = validated_data.pop("promotion_items", [])
        promotion = super().create(validated_data)

        # Lưu danh sách sản phẩm để cập nhật quan hệ M2M
        affected_products = set()

        promotion_items = []
        for item_data in promotion_items_data:
            product = item_data["product"]
            affected_products.add(product)
            promotion_items.append(PromotionItem(promotion=promotion, **item_data))

        # Tạo PromotionItem hàng loạt
        PromotionItem.objects.bulk_create(promotion_items)

        # Cập nhật M2M: Thêm promotion vào product.promotions
        for product in affected_products:
            product.promotions.add(promotion)

        return promotion

    @transaction.atomic
    def update(self, instance, validated_data):
        promotion_items_data = validated_data.pop("promotion_items", [])
        existing_items = {item.id: item for item in instance.promotion_items.all()}

        affected_products = set()
        new_items = []
        updated_items = []
        errors = []

        # Duyệt qua các promotion_items từ request
        for item_data in promotion_items_data:
            item_errors = {}
            item_id = item_data.get("id")
            product = item_data["product"]
            affected_products.add(product)

            if item_id:
                # Nếu có ID, kiểm tra xem item có tồn tại không
                promotion_item = existing_items.get(item_id)
                if not promotion_item:
                    item_errors["id"] = _("Không tìm thấy PromotionItem.")
                else:
                    # Cập nhật PromotionItem
                    promotion_item.discount_type = item_data["discount_type"]
                    promotion_item.discount_value = item_data["discount_value"]
                    updated_items.append(promotion_item)
            else:
                # Nếu không có ID, tạo mới PromotionItem
                new_items.append(PromotionItem(promotion=instance, **item_data))

            # Thêm lỗi vào danh sách errors, nếu không có lỗi thì thêm {} để cho đúng thứ tự index
            errors.append(item_errors)

        # Nếu có lỗi, trả về ngay mà không update DB
        if any(errors):
            raise ValidationError({"promotion_items": errors})

        # Xóa PromotionItem không có trong request
        existing_item_ids = {
            item["id"] for item in promotion_items_data if "id" in item
        }
        instance.promotion_items.exclude(id__in=existing_item_ids).delete()

        # Lưu cập nhật PromotionItem hàng loạt
        if updated_items:
            PromotionItem.objects.bulk_update(
                updated_items, ["discount_type", "discount_value"]
            )
        if new_items:
            PromotionItem.objects.bulk_create(new_items)

        # Cập nhật M2M: Thêm promotion vào product.promotions
        for product in affected_products:
            product.promotions.add(instance)

        return super().update(instance, validated_data)


class AttributeValueSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(write_only=True, required=False)
    image = serializers.ImageField(
        required=False, max_length=100, allow_null=True
    )  # dùng allow_null k dùng allow_empty_file=True vì không chấp nhận file rỗng
    remove_image = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = AttributeValue
        fields = ["id", "name", "value", "image", "remove_image"]

    def validate(self, data):
        # Kiểm tra nếu `remove_image = True` nhưng ảnh vẫn được gửi
        if data.get("remove_image", False) and "image" in data:
            raise serializers.ValidationError("Không thể vừa xóa vừa upload ảnh.")

        return data


class AttributeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    attribute_values = AttributeValueSerializer(
        many=True,
        allow_empty=False,
        min_length=1,
        error_messages={
            "min_length": _("Phải có ít nhất {min_length} giá trị."),
            "empty": _("Danh sách giá trị không được để trống."),
        },
    )

    class Meta:
        model = ProductAttribute
        fields = ["id", "name", "attribute_values"]


class VariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    sku = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=20,
        validators=[
            sku_validator,
        ],
        error_messages={
            "max_length": "Mã phân loại không được vượt quá 20 ký tự.",
        },
    )
    image = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100000000"),
        max_digits=10,
        decimal_places=decimal_places,
        error_messages={
            "min_value": _("Giá phải lớn hơn hoặc bằng {min_value}."),
            "max_value": _("Giá phải nhỏ hơn hoặc bằng {max_value}.").format(
                max_value=number_format(
                    100000000, decimal_pos=decimal_places, force_grouping=True
                )
            ),
            "max_digits": _("Giá không được quá {max_digits} chữ số."),
            "null": _("Giá không được để trống."),
            "invalid": _("Giá phải là số lớn hơn hoặc bằng 0."),
            "max_decimal_places": _("Giá phải là số nguyên lớn hơn hoặc bằng 0."),
            "required": _("Giá không được để trống."),
        },
    )
    discount_price = serializers.DecimalField(
        max_digits=10, decimal_places=0, read_only=True
    )
    discount = serializers.DecimalField(max_digits=3, decimal_places=0, read_only=True)
    discount_display = serializers.CharField(read_only=True)
    stock = serializers.IntegerField(
        min_value=0,
        max_value=100000000,
        error_messages={
            "min_value": _("Kho phải lớn hơn hoặc bằng {min_value}."),
            "max_value": _("Kho phải nhỏ hơn hoặc bằng {max_value}.").format(
                max_value=number_format(100000000, force_grouping=True)
            ),
            "null": _("Kho không được để trống."),
            "invalid": _("Kho phải là số lớn hơn hoặc bằng 0."),
            "max_decimal_places": _("Kho phải là số nguyên lớn hơn hoặc bằng 0."),
            "required": _("Kho không được để trống."),
        },
    )
    stock_setting = StockSettingSerializer(required=False)

    class Meta:
        model = Variant
        fields = [
            "id",
            "sku",
            "name",
            "image",
            "stock",
            "stock_setting",
            "price",
            "discount_price",
            "discount",
            "discount_display",
            "is_default",
        ]

    def get_image(self, obj):
        # nếu muốn URL trả về gồm cả domain thì sử dụng request.build_absolute_uri
        # request = self.context.get("request")
        # request.build_absolute_uri(settings.MEDIA_URL + obj.image)
        return (
            settings.MEDIA_URL + obj.image
            if hasattr(obj, "image") and obj.image
            else ""
        )


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name")
    rating_star = serializers.DecimalField(
        max_digits=2, decimal_places=1, required=False
    )
    cover_image = serializers.SerializerMethodField()
    total_stock = serializers.IntegerField(read_only=True)
    min_price = serializers.DecimalField(
        max_digits=10, decimal_places=0, read_only=True
    )
    max_price = serializers.DecimalField(
        max_digits=10, decimal_places=0, read_only=True
    )
    is_active = serializers.BooleanField(required=False, default=False)
    variants_count = serializers.IntegerField(read_only=True, required=False)
    low_stock_status = serializers.BooleanField(read_only=True, required=False)
    promotions = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "category",
            "cover_image",
            "rating_star",
            "total_stock",
            "min_price",
            "max_price",
            "is_active",
            "variants_count",
            "low_stock_status",
            "sale_count",
            "view_count",
            "search_count",
            "is_active",
            "variants",
            "promotions",
        ]

    def get_cover_image(self, obj):
        # Lấy đối tượng request từ context
        if hasattr(obj, "cover_image") and obj.cover_image:
            return settings.MEDIA_URL + obj.cover_image
        return ""

    def get_promotions(self, obj):
        request = self.context.get("request")
        include_promotion = request.query_params.get(
            "include_promotion", "false"
        ).strip().lower() in ["true", "1", "yes"]
        if include_promotion:
            promotions_data = []
            for promo in obj.promotions.all():
                promotion_data = {
                    "id": promo.id,
                    "name": promo.name,
                    "start_date": promo.start_date,
                    "end_date": promo.end_date,
                }
                if hasattr(promo, "min_price"):
                    promotion_data.min_price = promo.min_price
                if hasattr(promo, "max_price"):
                    promotion_data.max_price = promo.max_price
                promotions_data.append(promotion_data)
            return promotions_data
        return None

    def get_variants(self, obj):
        request = self.context.get("request")
        include_variants = request.query_params.get("include_variants", False)
        if include_variants:
            return VariantSerializer(obj.variants.all(), many=True).data
        return None

    def to_representation(self, instance):
        # Lấy dữ liệu mặc định từ serializer
        data = super().to_representation(instance)

        request = self.context.get("request")
        include_variants = request.query_params.get(
            "include_variants", "false"
        ).strip().lower() in ["true", "1", "yes"]
        include_promotion = request.query_params.get(
            "include_promotion", "false"
        ).strip().lower() in ["true", "1", "yes"]
        if not include_variants:
            data.pop("variants", None)  # Loại bỏ trường 'variants'
        if not include_promotion:
            data.pop("promotions", None)  # Loại bỏ trường 'promotions'
        return data


class ProductListPublicSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    variant_id = (
        serializers.IntegerField()
    )  # variant có giá thấp nhất (đã tính giám giá)
    rating_star = serializers.DecimalField(max_digits=2, decimal_places=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=0, read_only=True)
    discount_price = serializers.DecimalField(
        max_digits=10, decimal_places=0, read_only=True
    )
    discount = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "variant_id",
            "url",
            "name",
            "sku",
            "cover_image",
            "rating_star",
            "price",
            "discount_price",
            "discount",
            "is_active",
        ]

    def get_url(self, obj):
        # Ưu tiên url của variant có giá thấp nhất (đã tính giám giá)
        variant = Variant.objects.filter(pk=obj.variant_id).prefetch_related(
            "attribute_values"
        )
        if variant.exists():
            url = variant.first().get_absolute_url
            return url
        # Không có thì fallback url của product
        return obj.get_absolute_url

    def get_cover_image(self, obj):
        # Lấy đối tượng request từ context
        if hasattr(obj, "cover_image") and obj.cover_image:
            return settings.MEDIA_URL + obj.cover_image
        return ""


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(
        max_length=20,
        validators=[
            sku_validator,
            UniqueValidator(
                queryset=Product.objects.all(), message="Mã sản phẩm đã tồn tại."
            ),
        ],
        error_messages={
            "max_length": "Mã sản phẩm không được vượt quá 20 ký tự.",
            "blank": "Mã sản phẩm không được để trống.",
        },
    )
    name = serializers.CharField(
        required=False,
        min_length=10,
        max_length=150,
        error_messages={
            "min_length": _("Tên sản phẩm phải có ít nhất {min_length} ký tự."),
            "max_length": _("Tên sản phẩm không được vượt quá {max_length} ký tự."),
        },
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True, subcategory__isnull=True),
    )
    cover_image = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=False)
    description = serializers.CharField(
        allow_blank=True,
        allow_null=True,
        max_length=250,
        error_messages={
            "max_length": _("Mô tả sản phẩm không được vượt quá {max_length} ký tự."),
        },
    )
    detail = serializers.CharField(
        min_length=50,
        error_messages={
            "min_length": _("Chi tiết sản phẩm phải có ít nhất {min_length} ký tự."),
            "blank": _("Chi tiết sản phẩm không được để trống."),
            "required": _("Chi tiết sản phẩm không được để trống."),
            "null": _("Chi tiết sản phẩm không được để trống."),
        },
    )
    attributes = AttributeSerializer(many=True)
    variants = VariantSerializer(many=True)
    gallery = GallerySerializer(many=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "category",
            "cover_image",
            "description",
            "detail",
            "is_active",
            "attributes",
            "variants",
            "gallery",
        ]

    def get_cover_image(self, obj):
        # Lấy đối tượng request từ context
        if hasattr(obj, "cover_image") and obj.cover_image:
            return settings.MEDIA_URL + obj.cover_image
        return ""

    def validate_attributes(self, data):
        print(data)

    def validate(self, data):
        # Dữ liệu attributes và variants không phải một field trực tiếp của ProductSerializer
        # vì thế đã bị pop ra khỏi nên phải lấy từ initial_data không nên lấy từ data
        attributes_data = self.initial_data.get("attributes", [])
        variants_data = self.initial_data.get("variants", [])

        errors = {}

        if attributes_data:
            seen_names = set()
            attr_errors = []

            if len(attributes_data) > 2:
                errors["non_field_error"] = _(
                    "Số lượng thuộc tính phân loại chỉ cho phép tối đa 2."
                )
            # Tạo tổ hợp giá trị thuộc tính từ attributes_data
            valid_combinations = set(
                itertools_product(
                    *[
                        [val["value"] for val in attr["attribute_values"]]
                        for attr in attributes_data
                    ]
                )
            )

            # Kiểm tra số lượng variants có hợp lệ không
            if len(variants_data) != len(valid_combinations):
                errors["non_field_error"] = _(
                    "Số lượng phân loại không hợp lệ. Số phân loại đúng phải là: %s."
                ) % len(valid_combinations)
            for attr in attributes_data:
                attr_name = attr["name"]
                attr_error = {}

                # Kiểm tra trùng lặp
                if attr_name in seen_names:
                    attr_error["name"] = _("Tên phân loại bị trùng.")
                else:
                    seen_names.add(attr_name)

                seen_values = set()
                value_errors = []

                for values in attr.get("values", []):
                    value = values["value"]
                    if value in seen_values:
                        value_errors.append(
                            {"value": _("Giá trị thuộc tính bị trùng.")}
                        )  # Lỗi trùng
                    else:
                        value_errors.append({})  # Giữ đúng index nếu không lỗi
                        seen_values.add(value)

                # Nếu có lỗi thực sự (không tính {})
                if any(value_errors):
                    attr_error["values"] = value_errors

                attr_errors.append(attr_error)

            # Nếu có lỗi thực sự (không tính {})
            if any(attr_errors):
                errors["attributes"] = attr_errors

            seen_variants = set()
            variant_errors = []

            for variant in variants_data:
                variant_error = {}
                variant_values = variant.get("attribute_values", [])

                # Chuyển các value của attribute_values variant thành tuple để so sánh với tổ hợp hợp lệ
                variant_combination = tuple(
                    attr.get("value", "") for attr in variant_values
                )

                # Kiểm tra xem variant có trong tổ hợp hợp lệ không
                if variant_combination not in valid_combinations:
                    variant_error["attribute_values"] = (
                        _("Thuộc tính %s không hợp lệ.") % variant_combination
                    )

                # Kiểm tra trùng lặp variant
                elif variant_combination in seen_variants:
                    variant_error["attribute_values"] = _("Phân loại này bị trùng.")
                else:
                    seen_variants.add(variant_combination)

                variant_errors.append(variant_error)

            if any(variant_errors):
                errors["variants"] = variant_errors
        else:
            # Nếu không có attributes
            variant_error = {}

            if len(variants_data) != 1:
                variant_error["non_field_error"] = _(
                    "Số lượng phân loại không hợp lệ. Số phân loại đúng phải là: 1."
                )
            elif not variants_data[0].get("is_default", False):
                variant_error["is_default"] = _("Giá trị không hợp lệ, phải là True.")
            if variant_error:
                errors["variants"] = variant_error

        if errors:
            raise serializers.ValidationError(errors)

        return data

    @transaction.atomic
    def create(self, validated_data):
        attributes_data = validated_data.pop("attributes", [])
        variants_data = validated_data.pop("variants", [])
        gallery_data = validated_data.pop("gallery", [])

        # === Tạo Product ===
        product = Product.objects.create(**validated_data)

        # === Tạo Product Attributes & Values ===
        attr_value_map = {}

        for attr_data in attributes_data:
            values_data = attr_data.pop("attribute_values", [])
            attribute = ProductAttribute.objects.create(
                product=product, name=attr_data["name"]
            )

            for value_data in values_data:
                value = AttributeValue.objects.create(attribute=attribute, **value_data)
                attr_value_map[(attr_data["name"], value_data["value"])] = value

        if not attributes_data and len(variants_data) == 1:
            variants_data[0]["is_default"] = True

        # === Tạo Variants ===
        total_stock = 0
        min_price = 0
        max_price = None
        for var_data in variants_data:
            variant_attributes = var_data.pop("attribute_values", [])
            variant = Variant.objects.create(product=product, **var_data)

            # Cập nhật tổng stock
            total_stock += variant.stock or 0

            # Lấy giá min/max từ price (vì tạo mới chưa có add promotion vào)
            price = var_data["price"]
            if min_price is None or price < min_price:
                min_price = price
            if max_price is None or price > max_price:
                max_price = price

            attribute_instances = []
            for attr_data in variant_attributes:
                attr_name, attr_value = attr_data["name"], attr_data["value"]

                if (attr_name, attr_value) in attr_value_map:
                    attribute_instances.append(attr_value_map[(attr_name, attr_value)])
                else:
                    print(f"Phân loại '{attr_name}' - '{attr_value}' không tồn tại.")

            variant.attribute_values.set(attribute_instances)

        # === Tạo Gallery Images & Gán Cover Image ===
        for index, img_data in enumerate(gallery_data, start=1):
            gallery = Gallery.objects.create(
                product=product, image=img_data["image"], order=index
            )
            if index == 1:
                product.cover_image = gallery.image.url
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        attributes_data = validated_data.pop("attributes", [])
        variants_data = validated_data.pop("variants", [])
        gallery_data = validated_data.pop("gallery", [])
        product = super().update(instance, validated_data)

        existing_attributes = {
            a.id: a for a in ProductAttribute.objects.filter(product=product)
        }
        existing_values = {
            v.id: v for v in AttributeValue.objects.filter(attribute__product=product)
        }
        existing_variants = {v.id: v for v in Variant.objects.filter(product=product)}
        existing_galleries = {g.id: g for g in Gallery.objects.filter(product=product)}

        attr_ids, attr_value_ids, variant_ids, gallery_ids = set(), set(), set(), set()
        attr_value_map = {}

        # Khởi tạo biến errors theo format yêu cầu
        errors = {}

        # === Cập nhật Attributes ===
        attribute_errors = []
        if attributes_data:
            for attr_data in attributes_data:
                attr_id = attr_data.pop("id", None)
                values_data = attr_data.pop("attribute_values", [])

                attribute_error = {}  # Mỗi attribute có thể chứa lỗi ID và values

                if attr_id:
                    if attr_id not in existing_attributes:
                        attribute_error["name"] = _(
                            "Thuộc tính '%s' (ID %s) không tồn tại trong sản phẩm này."
                        ) % (attr_data["name"], attr_id)
                        attribute_errors.append(attribute_error)
                        continue  # Không xử lý tiếp nếu lỗi

                    attribute = existing_attributes[attr_id]
                    attribute.name = attr_data["name"]
                    attribute.save()
                else:
                    attribute = ProductAttribute.objects.create(
                        product=product, **attr_data
                    )

                attr_ids.add(attribute.id)

                # === Cập nhật Attribute Values ===
                attribute_value_errors = []

                for value_data in values_data:
                    value_id = value_data.pop("id", None)
                    if value_id:
                        if value_id not in existing_values:
                            attribute_value_errors.append(
                                {
                                    "id": _(
                                        "Giá trị '%s' (ID %s) không tồn tại trong sản phẩm này."
                                    )
                                    % (value_data["value"], value_id)
                                }
                            )
                            continue  # Không xử lý tiếp nếu lỗi

                        value = existing_values[value_id]
                        image = value_data.pop("image", False)
                        is_remove_image = value_data.pop("remove_image", False)
                        if is_remove_image:
                            value.image.delete(save=False)
                            value.image = None
                        elif image:
                            value.image = image
                        value.value = value_data["value"]
                        value.save()
                    else:
                        value = AttributeValue.objects.create(
                            attribute=attribute, **value_data
                        )

                    attr_value_ids.add(value.id)
                    attr_value_map[(attr_data["name"], value_data["value"])] = value

                    # Đảm bảo giữ vị trí đúng
                    attribute_value_errors.append({})

                # Nếu có lỗi trong values
                if any(attribute_value_errors):
                    attribute_error["attribute_values"] = attribute_value_errors

                # Giữ vị trí đúng
                attribute_errors.append(attribute_error)

            # Nếu có lỗi Attributes, thêm vào errors
            if any(attribute_errors):
                errors["attributes"] = attribute_errors

        # Xoá Attribute và Values không có trong list id
        ProductAttribute.objects.filter(product=product).exclude(
            id__in=attr_ids
        ).delete()
        AttributeValue.objects.filter(attribute__product=product).exclude(
            id__in=attr_value_ids
        ).delete()

        # === Cập nhật Variants ===
        variant_errors = []  # Danh sách lỗi của variants
        variants = []
        if not attributes_data and len(variants_data) == 1:
            variants_data[0]["is_default"] = True

        for var_data in variants_data:
            variant_error = {}
            var_id = var_data.pop("id", None)
            variant_attribute_data = var_data.pop("attribute_values", [])
            if var_id:
                if var_id not in existing_variants:
                    variant_error["id"] = (
                        _("Phân loại với ID %s không tồn tại trong sản phẩm này.")
                        % var_id
                    )
                    variant_errors.append(variant_error)
                    continue
                variant = existing_variants[var_id]
                for field, value in var_data.items():
                    setattr(variant, field, value)
                variant.save()
                variant_ids.add(variant.id)
            else:
                variant = Variant.objects.create(product=product, **var_data)
                variant_ids.add(variant.id)

            attribute_instances = []
            attribute_value_errors = (
                []
            )  # Danh sách lỗi của attribute_values trong variant
            for attr in variant_attribute_data:
                attr_name, attr_value = attr["name"], attr["value"]
                if (attr_name, attr_value) in attr_value_map:
                    attribute_instances.append(attr_value_map[(attr_name, attr_value)])
                    attribute_value_errors.append({})
                else:
                    attribute_value_errors.append(
                        {
                            "non_field_error": _(
                                "Phân loại với thuộc tính '%s' - '%s' không tồn tại."
                            )
                            % (attr_name, attr_value)
                        }
                    )

            variant.attribute_values.set(attribute_instances)
            # Lấy ảnh từ attribute value có ảnh đầu tiên
            variant.image = next(
                (attr.image.url for attr in attribute_instances if attr.image),
                "",  # Nếu không có ảnh nào, trả về chuỗi rỗng
            )
            variants.append(variant)

            # Nếu có lỗi trong attribute_values, thêm vào variant_error
            if any(attribute_value_errors):
                variant_error["attribute_values"] = attribute_value_errors

            # Giữ vị trí chính xác
            variant_errors.append(variant_error)

        # Nếu có lỗi trong variants, thêm vào errors
        if any(variant_errors):
            errors["variants"] = variant_errors

        # Xóa Variants không còn tồn tại
        Variant.objects.filter(product=product).exclude(id__in=variant_ids).delete()

        # === Cập nhật Gallery ===
        gallery_errors = []  # Danh sách lỗi của gallery

        for index, data in enumerate(gallery_data, start=1):
            gallery_error = {}
            gallery_id = data.get("id")
            if gallery_id:
                if gallery_id not in existing_galleries:
                    gallery_error["id"] = (
                        _("Ảnh với ID %s không tồn tại trong sản phẩm này.")
                        % gallery_id
                    )
                    gallery_errors.append(gallery_error)
                    continue
                gallery = existing_galleries[gallery_id]
                gallery.image = data.get("image", gallery.image)
                gallery.order = index
                gallery.save()
            else:
                gallery = Gallery.objects.create(
                    product=product, image=data.get("image"), order=index
                )
            if index == 1:
                product.cover_image = gallery.image.url
            gallery_ids.add(gallery.id)

            # Giữ vị trí chính xác
            gallery_errors.append(gallery_error)

        # Nếu có lỗi trong gallery, thêm vào errors
        if any(gallery_errors):
            errors["gallery"] = gallery_errors

        # Xoá Gallery không có trong danh sách
        Gallery.objects.filter(product=product).exclude(id__in=gallery_ids).delete()

        # Nếu có lỗi, rollback transaction
        if any(errors):
            transaction.set_rollback(True)
            raise serializers.ValidationError(errors)

        return product


class ProductVariantSerializer(serializers.ModelSerializer):
    cover_image = serializers.SerializerMethodField()
    total_stock = serializers.IntegerField(read_only=True)
    min_price = serializers.DecimalField(
        max_digits=10, decimal_places=0, read_only=True
    )
    max_price = serializers.DecimalField(
        max_digits=10, decimal_places=0, read_only=True
    )
    variants = VariantSerializer(many=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "cover_image",
            "total_stock",
            "min_price",
            "max_price",
            "variants",
            "is_active",
        ]

    def get_cover_image(self, obj):
        # Lấy đối tượng request từ context
        if hasattr(obj, "cover_image") and obj.cover_image:
            return settings.MEDIA_URL + obj.cover_image
        return ""


class VariantPriceStockSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    price = serializers.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100000000"),
        max_digits=10,
        decimal_places=decimal_places,
        error_messages={
            "min_value": _("Giá phải lớn hơn hoặc bằng {min_value}."),
            "max_value": _("Giá phải nhỏ hơn hoặc bằng {max_value}.").format(
                max_value=number_format(
                    100000000, decimal_pos=decimal_places, force_grouping=True
                )
            ),
            "max_digits": _("Giá không được quá {max_digits} chữ số."),
            "null": _("Giá không được để trống."),
            "invalid": _("Giá phải là số lớn hơn hoặc bằng 0."),
            "max_decimal_places": _("Giá phải là số nguyên lớn hơn hoặc bằng 0."),
            "required": _("Giá không được để trống."),
        },
    )
    add_stock = serializers.IntegerField(
        required=False,
        write_only=True,
        default=0,
        min_value=0,
        allow_null=True,
        error_messages={
            "min_value": _("Số lượng thêm phải lớn hơn hoặc bằng {min_value}."),
            "invalid": _("Số lượng thêm là số nguyên lớn hơn hoặc bằng 0."),
        },
    )
    stock_setting = StockSettingSerializer(required=False)

    class Meta:
        model = Variant
        fields = ["id", "price", "stock", "add_stock", "stock_setting"]
        read_only_fields = ["stock"]

    def get_cover_image(self, obj):
        # Lấy đối tượng request từ context
        if hasattr(obj, "cover_image") and obj.cover_image:
            return settings.MEDIA_URL + obj.cover_image
        return ""


class ProductVariantStockPriceUpdateSerializer(serializers.ModelSerializer):
    variants = VariantPriceStockSerializer(many=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "variants",
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        variants_data = validated_data["variants"]
        print(variants_data)
        errors = []
        variant_errors = []
        for variant_data in variants_data:
            variant_id = variant_data.get("id", None)
            variant_error = (
                {}
            )  # nếu không có lỗi thì dict rỗng giữ chỗ cho đúng index lỗi trong variant_errors

            try:
                variant = Variant.objects.get(product=instance, id=variant_id)
            except Variant.DoesNotExist:
                variant_error["id"] = _("Phân loại ID %s không tồn tại.") % variant_id
                variant_errors.append(variant_error)
                continue

            # Cập nhật giá
            new_price = variant_data.get("price")
            if new_price is not None:
                variant.price = new_price

            # Cập nhật tồn kho
            add_stock = variant_data.get("add_stock")
            if add_stock:
                variant.stock = F("stock") + add_stock

            variant.save(update_fields=("stock", "price"))

            # Cập nhật StockSetting
            stock_setting_data = variant_data.get("stock_setting", {})
            stock_setting, created = StockSetting.objects.get_or_create(variant=variant)

            for field, value in stock_setting_data.items():
                setattr(stock_setting, field, value)

            stock_setting.save()
            variant_errors.append(variant_error)

        if any(variant_error):
            errors.append({"variants": variant_errors})

        if any(errors):
            transaction.set_rollback(True)
            raise serializers.ValidationError(
                {"status": "failed", "errors": {"stock_update": errors}}
            )

        return instance


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "parent", "user", "product", "content", "timesince", "replies"]
        extra_kwargs = {
            "content": {
                "allow_blank": False,  # Không cho phép giá trị rỗng
            }
        }

    def get_replies(self, obj):
        """Lấy danh sách phản hồi của bình luận"""
        return CommentSerializer(obj.replies, many=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user = instance.user  # Truy cập đối tượng user liên kết
        representation["user"] = {
            "id": user.id,
            "avatar": user.avatar.url if user.avatar else None,
            "full_name": user.full_name,
        }
        return representation

    def create(self, validated_data):
        """Tạo bình luận mới và chỉ cho phép user đăng nhập"""
        user = self.context["request"].user
        validated_data["user"] = user  # Đảm bảo user là người đang đăng nhập
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    comment = CommentSerializer(required=False, allow_null=True)
    content = serializers.CharField(write_only=True)  # Chỉ nhập vào, không trả về

    class Meta:
        model = Review
        fields = ["id", "user", "comment", "product", "score", "content", "timesince"]
        read_only_fields = ["user"]  # Không cho phép gửi user từ client

    def to_representation(self, instance):
        """Hiển thị thông tin user & review chi tiết hơn"""
        representation = super().to_representation(instance)
        user = instance.user
        representation["user"] = {
            "id": user.id,
            "full_name": user.full_name,
            "avatar": user.avatar.url if user.avatar else None,
        }
        return representation

    def create(self, validated_data):
        """Tạo review mới & đảm bảo user đang đăng nhập"""
        user = self.context["request"].user  # Lấy user đang đăng nhập
        validated_data["user"] = user  # Gán user vào review

        # Lấy nội dung comment nếu có
        content = validated_data.pop("content", "").strip()
        if content:
            comment = Comment.objects.create(
                user=user, product=validated_data["product"], content=content
            )
            validated_data["comment"] = comment  # Gán comment vào review

        return Review.objects.create(**validated_data)


class CartItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = CartItem
        fields = ["id", "quantity", "product", "variant"]

    def to_representation(self, instance):
        """Ghi đè dữ liệu trả về, sử dụng giá trị từ annotate"""
        data = super().to_representation(instance)

        # Lấy dữ liệu product đã annotate
        data["product"] = {
            "id": instance.product.id,
            "name": instance.product.name,
            "cover_image": (
                settings.MEDIA_URL + instance.product.cover_image
                if instance.product.cover_image
                else settings.MEDIA_URL + default_no_image
            ),  # Lấy từ annotate
        }

        # Lấy dữ liệu variant đã annotate
        if instance.variant:
            data["variant"] = {
                "id": instance.variant.id,
                "name": instance.variant.name,
                "price": float(instance.variant.price),
                "stock": instance.variant.stock,
                "discount_price": float(
                    instance.variant.discount_price
                ),  # Lấy từ annotate
                "image": (
                    settings.MEDIA_URL + instance.variant.image
                    if instance.variant.image
                    else ""
                ),  # Lấy từ annotate
                "url": instance.variant.get_absolute_url,
            }

        return data

    @transaction.atomic
    def create(self, validated_data):
        """Xử lý tạo mới CartItem"""
        user = self.context["request"].user
        product = validated_data["product"]
        variant = validated_data.get("variant")
        quantity = validated_data["quantity"]
        # Lấy hoặc tạo giỏ hàng
        cart, ignore = Cart.objects.get_or_create(user=user)
        # Kiểm tra sản phẩm đã có trong giỏ hàng chưa
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, variant=variant
        )

        # Kiểm tra tồn kho
        stock = cart_item.variant.stock
        if quantity > stock:
            raise serializers.ValidationError(
                {"quantity": _("Không đủ hàng trong kho.")}
            )

        # Cập nhật số lượng
        cart_item.quantity += quantity
        cart_item.save()

        return cart_item

    @transaction.atomic
    def update(self, instance, validated_data):
        """Xử lý cập nhật số lượng CartItem"""
        quantity = validated_data.get("quantity", instance.quantity)

        # Kiểm tra tồn kho
        stock = instance.variant.stock
        if quantity > stock:
            raise serializers.ValidationError(
                {"quantity": _("Không đủ hàng trong kho.")}
            )

        instance.quantity = quantity
        instance.save()

        return instance


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, source="cart_items")
    total_items = serializers.IntegerField(read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["total_price", "total_items", "items"]

    def get_total_price(self, obj):
        """Tính tổng tiền của cả giỏ hàng"""
        total_price = sum(item.get_total_price() for item in obj.cart_items.all())
        return float(total_price)


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        required=False,
        min_value=Decimal("1"),
        max_value=Decimal("100000000"),
        max_digits=10,
        decimal_places=decimal_places,
        error_messages={
            "min_value": _("Số tiền thanh toán phải lớn hơn hoặc bằng {min_value}."),
            "max_value": _(
                "Số tiền thanh toán phải nhỏ hơn hoặc bằng {max_value}."
            ).format(
                max_value=number_format(
                    100000000, decimal_pos=decimal_places, force_grouping=True
                )
            ),
            "max_digits": _("Số tiền thanh toán không được quá {max_digits} chữ số."),
            "null": _("Số tiền thanh toán không được để trống."),
            "invalid": _("Số tiền thanh toán phải là số lớn hơn hoặc bằng 0."),
            "max_decimal_places": _(
                "Số tiền thanh toán phải là số nguyên lớn hơn hoặc bằng 0."
            ),
        },
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "user",
            "payment_method",
            "transaction_id",
            "amount",
            "status",
            "paid_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "paid_at"]

    def validate(self, attrs):
        """Custom validation logic"""
        payment_method = attrs.get("payment_method")
        transaction_id = attrs.get("transaction_id")
        status = attrs.get("status")
        paid_at = attrs.get("paid_at")

        if payment_method != "cod" and not transaction_id:
            raise serializers.ValidationError(
                {"transaction_id": _("Cổng thanh toán yêu cầu transaction_id hợp lệ.")}
            )

        if status == "paid" and not paid_at:
            attrs["paid_at"] = now()
        elif status != "paid" and paid_at:
            raise serializers.ValidationError(
                {
                    "paid_at": _(
                        "Chỉ có thể đặt thời gian thanh toán nếu đơn hàng đã thanh toán."
                    )
                }
            )

        return attrs


class OrderItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "variant",
            "name",
            "image",
            "attributes",
            "quantity",
            "price",
            "discount_price",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.ListField(write_only=True, child=serializers.DictField())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    order_items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer()
    payment = PaymentSerializer()

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "shipping_address",
            "payment",
            "total_price",
            "shipping_cost",
            "status",
            "order_items",
            "items",
        ]
        read_only_fields = ["id", "status", "total_price"]

    def create(self, validated_data):
        """Tạo mới đơn hàng, xử lý trừ kho và Payment"""
        items_data = validated_data.pop("items", [])
        shipping_address_data = validated_data.pop("shipping_address", {})
        payment_data = validated_data.pop("payment", None)
        user = validated_data.get("user")
        errors = {}
        # Tạo hoặc lấy địa chỉ giao hàng
        shipping_address_id = shipping_address_data.pop(
            "id", None
        )  # None nếu không có ID
        if shipping_address_id:
            try:
                shipping_address = UserShippingAddress.objects.get(
                    id=shipping_address_id,
                    user=user,  # phải là địa chỉ giao hàng của chính User đó
                )
            except UserShippingAddress.DoesNotExist:
                errors["shipping_address"] = {
                    "id": _("Địa chỉ giao hàng không tồn tại")
                }
        else:
            shipping_address = UserShippingAddress.objects.create(
                user=user, **shipping_address_data
            )

        # Tạo đơn hàng
        order = Order.objects.create(
            shipping_address=shipping_address, **validated_data
        )

        # Danh sách lỗi
        item_errors = [
            {} for _ in range(len(items_data))
        ]  # Mảng lỗi cùng số lượng items
        order_items = []
        total_price = 0

        for index, item_data in enumerate(items_data):
            product_id = item_data.get("product_id")
            variant_id = item_data.get("variant_id")
            quantity = item_data.get("quantity", 0)

            variant = (
                Variant.objects.filter(id=variant_id, product__id=product_id)
                .select_related("product")
                .annotate(
                    discount_price=Case(
                        When(
                            promotion_items__isnull=False,
                            promotion_items__discount_type="percent",
                            promotion_items__promotion__start_date__lte=now(),
                            promotion_items__promotion__end_date__gt=now(),
                            then=F("price")
                            * (1 - F("promotion_items__discount_value") / 100),
                        ),
                        When(
                            promotion_items__isnull=False,
                            promotion_items__discount_type="amount",
                            promotion_items__promotion__start_date__lte=now(),
                            promotion_items__promotion__end_date__gt=now(),
                            then=F("price") - F("promotion_items__discount_value"),
                        ),
                        default=F("price"),
                        output_field=models.DecimalField(
                            max_digits=10, decimal_places=2
                        ),
                    )
                )
                .first()
            )

            # Kiểm tra lỗi
            if not variant:
                item_errors[index]["variant"] = _("Phân loại sản phẩm không tồn tại.")

            if quantity > variant.stock:
                item_errors[index]["quantity"] = _("Sản phẩm không đủ hàng trong kho.")

            # Nếu có lỗi thì bỏ qua item này
            if item_errors[index]:
                continue

            attribute_image = variant.attribute_values.filter(
                image__isnull=False
            ).first()

            if attribute_image and attribute_image.image:
                source_image = attribute_image.image  # Ảnh từ attribute_values
            elif variant.product.gallery.filter(order=1).exists():
                source_image = (
                    variant.product.gallery.filter(order=1).first().image
                )  # Ảnh từ gallery
            else:
                source_image = None  # Không có ảnh

            if source_image:
                # Đọc nội dung ảnh gốc
                with source_image.open("rb") as image_file:
                    image_content = image_file.read()
                    filename = image_file.name.split("/")[-1]
                    # Lưu ảnh mới vào OrderItem
                    item_data["image"] = ContentFile(image_content, filename)
            else:
                item_data["image"] = (
                    default_no_image  # Ảnh mặc định nếu không có ảnh gốc
                )
            item_data["name"] = variant.product.name
            item_data["attributes"] = variant.name
            item_data["price"] = variant.price
            item_data["discount_price"] = variant.discount_price

            total_price += quantity * (
                variant.discount_price if variant.discount_price else variant.price
            )
            order_item = OrderItem(order=order, **item_data)
            order_items.append(order_item)

        # Nếu có lỗi thì trả về response lỗi
        if any(item_errors):
            raise serializers.ValidationError({"items": item_errors})

        # Lưu danh sách sản phẩm vào DB
        OrderItem.objects.bulk_create(order_items)

        # Cập nhật tổng giá trị đơn hàng
        order.total_price = total_price
        order.save()

        # Payment**
        if payment_data:
            payment_data["user"] = user.id
            payment_data["amount"] = total_price
            payment_data["order"] = order.id
            payment_serializer = PaymentSerializer(data=payment_data)
            if payment_serializer.is_valid():
                payment_serializer.save()
            else:
                raise serializers.ValidationError(payment_serializer.errors)

        OrderStatusHistory.create_history(order)

        return order


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "is_read", "created_at"]


class ChatUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatUser
        fields = ["id", "name", "phone_number", "email"]


class ChatRoomSerializer(serializers.ModelSerializer):

    class Meta:
        model = ChatRoom
        fields = ["id", "name", "recipient", "status", "created_by"]

    def to_representation(self, instance):
        # Lấy dữ liệu mặc định của serializer
        representation = super().to_representation(instance)

        # Tùy chỉnh thông tin recipient (id và name)
        recipient = instance.recipient
        if recipient:
            representation["recipient"] = {
                "id": recipient.id,
                "name": recipient.full_name,
            }

        # Thay đổi status bằng status display
        representation["status"] = instance.get_status_display()

        return representation
