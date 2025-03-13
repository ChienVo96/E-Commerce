import os, string, random
from django.urls import reverse
from django.utils import timesince
from django.utils.timezone import now

from django.utils.text import capfirst
from django.db import models
from django.db.models import (
    Case,
    When,
    OuterRef,
    Q,
    F,
    Value,
    DecimalField,
    FloatField,
    ExpressionWrapper,
    Subquery,
)
from django.core.exceptions import ValidationError
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    MinLengthValidator,
    MaxLengthValidator,
    RegexValidator,
)
from django.utils.text import slugify
from PIL import Image
from django.contrib.admin.decorators import display
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .managers import UserManager, VariantManager
from django.utils.safestring import mark_safe
from django_ckeditor_5.fields import CKEditor5Field
from django.db.models import UniqueConstraint
import unicodedata
from django.utils.formats import number_format
from django.utils.timezone import localtime
from django.utils.http import urlencode
from django.utils.crypto import get_random_string
import os

default_no_image = "images/NoImage.png/"

decimal_places = 0

sku_validator = RegexValidator(
    regex="^[a-zA-Z0-9]+$",  # Chỉ cho phép chữ cái không dấu và số (a-z, A-Z, 0-9)
    message="SKU chỉ được chứa chữ IN HOA, số, dấu '-' hoặc '_'",
)

phone_number_validator = RegexValidator(
    regex=r"^\+?\d{10,15}$",  # Biểu thức chính quy kiểm tra số điện thoại có từ 10 đến 15 chữ số
    message="Số điện thoại phải có từ 10 đến 15 chữ số.",
    code="invalid_phone_number",
)


def generate_random_string(size=10):
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(size))


def generate_unique_invoice(instance, prefix="VN-"):
    # Get the current date
    today = now()
    # Format the date as YYYYMMDD
    date_prefix = today.strftime("%Y%m%d")

    # Get the model class from the instance
    Klass = instance.__class__

    # Query for the last invoice number with the same date prefix
    last_invoice = (
        Klass.objects.filter(invoice__startswith=f"{prefix}{date_prefix}")
        .order_by("id")
        .last()
    )

    # Determine the next invoice number
    if last_invoice:
        last_number = int(last_invoice.invoice[len(f"{prefix}{date_prefix}") :])
        new_number = last_number + 1
    else:
        new_number = 1

    # Return the new unique invoice number
    return f"{prefix}{date_prefix}{new_number:04d}"


def generate_unique_slug(instance, field_name="name", field_sku=None, new_slug=None):
    max_length = instance._meta.get_field("slug").max_length

    # Generate the initial slug
    if new_slug is not None:
        slug = new_slug
    else:
        slug = slugify(f"{getattr(instance, field_name)}")
        if field_sku:
            slug = f"{slug}-{getattr(instance, field_sku)}"

    # Truncate the slug to fit within the max_length
    slug = slug[:max_length]

    # Ensure the slug is unique
    Klass = instance.__class__
    qs_exists = Klass.objects.filter(slug=slug).exclude(pk=instance.pk).exists()
    if qs_exists:
        # If the slug already exists, generate a new one with a random string
        random_str = generate_random_string(4)
        # Combine the base slug and random string, then ensure the total length is <= max_length
        new_slug = (
            f"{slug[:max_length-5]}-{random_str}"  # Ensure enough room for random_str
        )

        # Check if new_slug still fits within the max_length
        if len(new_slug) > max_length:
            new_slug = new_slug[:max_length]
        return generate_unique_slug(instance, new_slug=new_slug)

    return slug


def image_upload_to(instance, filename):
    model_name = str(instance.__class__.__name__)
    if model_name == "Category":
        return os.path.join("images", "category", str(instance.name).lower(), filename)
    if model_name == "Gallery":
        return os.path.join(
            "images", "product", str(instance.product).lower(), filename
        )
    if model_name == "AttributeValue":
        return os.path.join(
            "images", "product", str(instance.attribute.product).lower(), filename
        )
    if model_name == "OrderItem":
        return os.path.join(
            "images", "order", str(instance.order.invoice).lower(), filename
        )
    return os.path.join(
        "images", str(model_name).lower(), str(instance).lower(), filename
    )


def notification_image_upload_to(instance, filename):
    # Lấy loại thông báo
    notification_type = instance.notification_type
    # Kiểm tra loại thông báo và tạo đường dẫn tương ứng
    if notification_type == "ORDER_STATUS":
        return f"images/notification/order_status/{instance.user.id}/{filename}"
    elif notification_type == "ACCOUNT":
        return f"images/notification/account/{instance.user.id}/{filename}"
    elif notification_type == "PROMOTION":
        return f"images/notification/promotion/{filename}"
    elif notification_type == "GENERAL":
        return f"images/notification/general/{filename}"
    else:
        return f"images/notification/other/{filename}"


def resize_image(image_field, max_size=(1024, 1024)):
    """
    Resize the image if it exceeds the specified max dimensions.

    Parameters:
    image_field: ImageField
        The image field to be resized.
    max_size: tuple
        Maximum allowed dimensions for the image (width, height).
    """
    if image_field and os.path.exists(image_field.path):
        img = Image.open(image_field.path)
        if img.height > max_size[0] or img.width > max_size[1]:
            img.thumbnail(max_size)
            img.save(image_field.path)


def normalize_text(text):
    """Chuẩn hoá chuỗi sang dạng NFC"""
    return unicodedata.normalize("NFC", text)


class CustomImageField(models.ImageField):
    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop("max_size", None)  # Kích thước tối đa (bytes)
        self.allowed_types = kwargs.pop(
            "allowed_types", ["image/jpeg", "image/png"]
        )  # Loại ảnh hợp lệ
        self.max_resolution = kwargs.pop(
            "max_resolution", None
        )  # (width, height) tối đa
        super().__init__(*args, **kwargs)

    def clean(self, value, model_instance):
        file = value.file

        # ✅ Kiểm tra kích thước file
        if self.max_size and file.size > self.max_size:
            raise ValidationError(
                _("Dung lượng tối đa là %d MB.") % (self.max_size / (1024 * 1024))
            )

        # ✅ Kiểm tra loại tệp
        if (
            hasattr(file, "content_type")
            and self.allowed_types
            and file.content_type not in self.allowed_types
        ):
            raise ValidationError(
                _("Loại ảnh không hợp lệ. Chỉ chấp nhận: %s")
                % ", ".join(self.allowed_types)
            )

        # ✅ Kiểm tra độ phân giải
        try:
            with Image.open(file) as img:
                img.verify()
                width, height = img.size

                if self.max_resolution:
                    max_width, max_height = self.max_resolution
                    if width > max_width or height > max_height:
                        raise ValidationError(
                            _("Kích thước tối đa là %dx%d px.")
                            % (max_width, max_height)
                        )

        except Exception:
            raise ValidationError(_("Tệp không phải là hình ảnh hợp lệ."))

        return super().clean(value, model_instance)


class CustomTextField(models.TextField):
    def get_prep_value(self, value):
        # Chuẩn hóa Unicode thành NFC trước khi lưu vào cơ sở dữ liệu
        if value:
            value = unicodedata.normalize("NFC", value)
        return super().get_prep_value(value)


class CustomCharField(models.CharField):

    def get_prep_value(self, value):
        # Chuẩn hóa Unicode thành NFC trước khi lưu vào cơ sở dữ liệu
        if value:
            value = unicodedata.normalize("NFC", value)
        return super().get_prep_value(value)


class User(AbstractBaseUser, PermissionsMixin):
    gender_choices = [
        ("male", _("Nam")),
        ("female", _("Nữ")),
        ("other", _("Khác")),
    ]
    email = models.EmailField("Email", unique=True)
    phone_number = models.CharField(
        _("Điện thoại"),
        unique=True,
        validators=[phone_number_validator],
        max_length=20,
        null=True,
        blank=True,
    )
    full_name = models.CharField(_("Họ và Tên"), max_length=50)
    gender = models.CharField(
        _("Giới Tính"), choices=gender_choices, null=True, blank=True, max_length=20
    )
    avatar = CustomImageField(
        _("Ảnh đại diện"),
        default="images/NoAvatar.png",
        upload_to=image_upload_to,
        max_size=1 * 1024 * 1024,
        max_resolution=(1024, 1024),
        allowed_types=["image/jpeg", "image/png"],
    )
    address = models.CharField(_("Địa chỉ"), max_length=200, blank=True, null=True)
    birth = models.DateField(_("Ngày Sinh"), blank=True, null=True)
    is_active = models.BooleanField(_("Kích hoạt"), default=False)
    is_vendor = models.BooleanField(_("Vendor"), default=False)
    is_staff = models.BooleanField(_("Quản Lý"), default=False)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày cập nhật"), auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()
    search_fields = ("email", "phone_number")
    ordering = ("email",)

    class Meta:
        verbose_name = _("Tài Khoản")
        verbose_name_plural = _("Tài Khoản")

    def __str__(self):
        return self.email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self._meta.fields:
            if field.unique:
                field.error_messages = {
                    "unique": _("%s đã tồn tại.")
                    % capfirst(field.verbose_name.lower()),
                }
            if hasattr(field, "required") and field.required:
                field.error_messages = {
                    "required": _("%s không được để trống.")
                    % capfirst(field.verbose_name),
                }

    @display(description=_("Xem trước Avatar"))
    def preview_avatar(self):
        if self.avatar:
            return mark_safe(f'<img src="{self.avatar.url}" width="64" height="64" />')
        return mark_safe(
            f'<img src="{settings.MEDIA_URL}{default_no_image}" width="64" height="64" />'
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Category(models.Model):
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Danh Mục Cha"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcategory",
    )
    name = CustomCharField(_("Tên Danh Mục"), max_length=255)
    image = models.ImageField(
        _("Hình Ảnh"),
        upload_to=image_upload_to,
        null=True,
        blank=True,
        default="images/NoImage.png",
    )
    slug = models.SlugField(unique=True, max_length=100, null=True, blank=True)
    is_active = models.BooleanField(_("Kích Hoạt"), default=True)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày cập nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Danh Mục")
        verbose_name_plural = _("Danh Mục")

    def __str__(self):
        return self.name

    def clean(self):
        """
        Kiểm tra name không trùng toàn bộ nếu là danh mục cha,
        và không trùng trong cùng một parent nếu là subcategory.
        """
        name = self.name.strip()  # Chuyển thành chữ thường

        if self.parent:
            # Kiểm tra trùng tên trong cùng một parent (không phân biệt hoa thường)
            if (
                Category.objects.filter(parent=self.parent, name__iexact=name)
                .exclude(id=self.id)
                .exists()
            ):
                raise ValidationError(_("Subcategory name '%s' is duplicate.") % name)
        else:
            # Kiểm tra nếu là danh mục cha, không cho phép trùng tên trong toàn bộ DB
            if (
                Category.objects.filter(parent__isnull=True, name__iexact=name)
                .exclude(id=self.id)
                .exists()
            ):
                raise ValidationError(
                    {"name": _("A category with this name already exists.")}
                )

    def save(self, *args, **kwargs):
        self.clean()
        if not self.pk and not self.slug:
            self.slug = generate_unique_slug(self)
        elif self.pk:
            # Nếu tên sản phẩm đã thay đổi, tạo lại slug
            current_name = Category.objects.get(pk=self.pk).name
            if current_name != self.name:
                self.slug = generate_unique_slug(self)
        super().save(*args, **kwargs)

    @display(description=_("Xem trước"))
    def preview_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="64" height="64" />')
        return mark_safe(
            f'<img src="{settings.MEDIA_URL}{default_no_image}" width="64" height="64" />'
        )


class Product(models.Model):
    sku = models.CharField(
        "Mã Sản Phẩm",
        max_length=20,
        unique=True,
        validators=[sku_validator],
        error_messages={
            "unique": "Mã sản phẩm đã tồn tại.",
            "blank": "Mã sản phẩm không được để trống.",
            "max_length": "Mã sản phẩm không được dài quá 20 ký tự.",
        },
    )
    name = CustomCharField(
        _("Tên Sản Phẩm"),
        max_length=150,
        validators=[
            MinLengthValidator(10, "Tên sản phẩm phải có ít nhất 10 ký tự."),
            MaxLengthValidator(150, "Tên sản phẩm không được vượt quá 150 ký tự."),
        ],
    )
    slug = models.SlugField(unique=True, max_length=150, null=True, blank=True)
    category = models.ForeignKey(
        "Category",
        verbose_name=_("Danh Mục"),
        on_delete=models.CASCADE,
        related_name="products",
    )
    description = CKEditor5Field(
        _("Mô Tả"), config_name="default", max_length=250, null=True, blank=True
    )
    detail = CKEditor5Field(
        _("Chi Tiết"),
    )
    is_active = models.BooleanField(_("Kích Hoạt"), default=True)
    sale_count = models.PositiveIntegerField(_("Đã Bán"), default=0)
    view_count = models.PositiveIntegerField(_("Lượt Xem"), default=0)
    search_count = models.PositiveIntegerField(_("Lượt Tìm Kiếm"), default=0)
    promotions = models.ManyToManyField(
        "Promotion", related_name="products", blank=True
    )
    created_by = models.ForeignKey(
        User,
        verbose_name=_("Người Tạo"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Sản Phẩm")
        verbose_name_plural = _("Sản Phẩm")
        ordering = ["-created_at"]

    def __str__(self):
        return self.sku

    def save(self, *args, **kwargs):
        # Tạo slug nếu chưa có
        if not self.pk and not self.slug:
            self.slug = generate_unique_slug(self, field_sku="sku")
        elif self.pk:
            # Nếu tên sản phẩm đã thay đổi, tạo lại slug
            old_name = Product.objects.get(pk=self.pk).name
            new_name = self.name
            if old_name and old_name != new_name:
                self.slug = generate_unique_slug(self, field_sku="sku")

        super().save(*args, **kwargs)  # Lưu sản phẩm trước

    def get_absolute_url(self):
        slug = self.slug
        return reverse("store:product_detail", kwargs={"slug": slug})

    @display(description=_("Xem trước Hình ảnh"))
    def preview_image(self):
        cover_image = self.gallery.filter(order=1).first()
        if cover_image and cover_image.image:
            return mark_safe(
                f'<img src="{cover_image.image.url}" width="64" height="64" />'
            )
        fallback_image = self.gallery.first()
        if fallback_image and fallback_image.image:
            return mark_safe(
                f'<img src="{fallback_image.image.url}" width="64" height="64" />'
            )
        return mark_safe(
            f'<img src="{settings.MEDIA_URL}{default_no_image}" width="64" height="64" />'
        )

    def get_variant_lowest_price(self):
        "Lấy biến thể có giá thấp nhất của sản phẩm sau khi đã tính khuyến mãi"

        # Lấy khuyến mãi hợp lệ
        valid_promotions = Q(
            promotion_items__isnull=False,
            promotion_items__promotion__start_date__lte=now(),
            promotion_items__promotion__end_date__gte=now(),
        )

        variant_lowest_price = (
            self.variants.filter(valid_promotions)
            .annotate(
                discount_price=Case(
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="amount",
                        then=F("price") - F("promotion_items__discount_value"),
                    ),
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="percent",
                        then=F("price")
                        * (1 - F("promotion_items__discount_value") / 100),
                    ),
                    default=F("price"),
                    output_field=DecimalField(),
                ),
                discount=Case(
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="amount",
                        then=ExpressionWrapper(
                            (F("promotion_items__discount_value") / F("price")) * 100,
                            output_field=FloatField(),
                        ),
                    ),
                    When(
                        promotion_items__promotion__start_date__lte=now(),
                        promotion_items__promotion__end_date__gt=now(),
                        promotion_items__discount_type="percent",
                        then=F("promotion_items__discount_value"),
                    ),
                    default=Value(0),
                    output_field=FloatField(),
                ),
                image=Subquery(
                    AttributeValue.objects.filter(
                        Q(variants=OuterRef("pk"))
                        & Q(image__isnull=False)
                        & ~Q(image=""),
                    ).values("image")[:1]
                ),
            )
            .order_by("discount_price")
            .first()
        )

        if not variant_lowest_price:
            variant_lowest_price = (
                self.variants.annotate(
                    discount_price=F("price"),
                    discount=Value(0, output_field=FloatField()),
                    image=Subquery(
                        Variant.objects.filter(
                            id=OuterRef("id"),
                            attribute_values__image__isnull=False,
                        ).values("attribute_values__image")[:1]
                    ),
                )
                .order_by("discount_price")
                .first()
            )
        return variant_lowest_price
        # endregion

    def update_sales_count(self, quantity):
        """Cập nhật số lượng sản phẩm đã bán"""
        self.sale_count += quantity
        self.save(update_fields=["sale_count"])


class ProductAttribute(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name=_("Sản Phẩm"),
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    name = models.CharField(_("Tên Thuộc Tính"), max_length=255)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày cập nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Thuộc Tính Sản Phẩm")
        verbose_name_plural = _("Thuộc Tính Sản Phẩm")
        unique_together = ["product", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class AttributeValue(models.Model):
    image = CustomImageField(
        _("Hình Ảnh"),
        upload_to=image_upload_to,
        max_size=2 * 1024 * 1024,
        max_resolution=(1280, 1280),
        null=True,
        blank=True,
    )
    attribute = models.ForeignKey(
        "ProductAttribute",
        verbose_name=_("Thuộc Tính"),
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )
    value = models.CharField(_("Giá Trị"), max_length=100)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Giá Trị Thuộc Tính")
        verbose_name_plural = _("Giá Trị Thuộc Tính")
        constraints = [
            UniqueConstraint(
                fields=["attribute", "value"], name="unique_attribute_value"
            )  # Ngăn chặn trùng lặp
        ]

    def __str__(self):
        return f"{self.attribute.name} {self.value}"

    @display(description=_("Xem trước Hình ảnh"))
    def preview_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="64" height="64" />')
        return mark_safe(
            f'<img src="{settings.MEDIA_URL}{default_no_image}" width="64" height="64" />'
        )


class Variant(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name=_("Sản Phẩm"),
        on_delete=models.CASCADE,
        related_name="variants",
    )
    sku = models.CharField(_("Sku"), max_length=20, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    price = models.DecimalField(
        _("Giá"),
        default=0,
        max_digits=12,
        decimal_places=decimal_places,
        validators=[MinValueValidator(0), MaxValueValidator(9999999999)],
    )
    stock = models.PositiveIntegerField(_("Kho"), default=0)
    attribute_values = models.ManyToManyField(
        AttributeValue,
        verbose_name=_("Giá Trị Thuộc Tính"),
        related_name="variants",
        blank=True,
    )
    is_default = models.BooleanField(_("Mặc Định"), default=False)
    created_by = models.ForeignKey(
        User,
        verbose_name=_("Người Tạo"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    objects = VariantManager()

    class Meta:
        verbose_name = _("Phân Loại Sản Phẩm")
        verbose_name_plural = _("Phân Loại Sản Phẩm")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} - {self.name}" if self.name else self.product.name

    @display(description=_("Xem trước Hình ảnh"))
    def preview_image(self):
        for attr_value in self.attribute_values.all():
            image = attr_value.image
            if image:
                return mark_safe(f'<img src="{image.url}" width="64" height="64" />')
        return mark_safe(
            f'<img src="{settings.MEDIA_URL}{default_no_image}" width="64" height="64" />'
        )

    @property
    def get_absolute_url(self):
        """Trả về URL đầy đủ của sản phẩm"""
        attr_values = self.attribute_values.values_list("id", flat=True)
        query_params = urlencode(
            [("attr_value", attr_value) for attr_value in attr_values]
        )
        base_url = self.product.get_absolute_url()
        url = f"{base_url}?{query_params}" if query_params else base_url
        return url

    def update_name(self):
        """Cập nhật tên variant dựa trên attribute_values."""
        if not self.attribute_values.exists():
            return  # Không có attribute_values thì không cập nhật name

        # Lấy danh sách giá trị thuộc tính
        attribute_names = self.attribute_values.values_list(
            "value", flat=True
        ).order_by("attribute__name")

        # Tạo tên từ danh sách thuộc tính, ví dụ: "Trắng, S"
        name = ", ".join(attribute_names)

        # Cập nhật tên nếu chưa có hoặc khi thuộc tính thay đổi
        if self.name != name:
            self.name = name
            self.save(update_fields=["name"])

    def update_stock(self, quantity, increase=False):
        """Cập nhật số lượng tồn kho một cách an toàn."""
        if quantity == 0:
            return

        if increase:
            # Tăng số lượng (trả hàng, hủy đơn)
            Variant.objects.filter(id=self.id).update(stock=F("stock") + quantity)
        else:
            # Giảm số lượng (đặt hàng), kiểm tra đủ tồn kho trước khi giảm
            # Nếu không đủ stock, updated_rows == 0, tránh trừ nhầm
            updated_rows = Variant.objects.filter(
                id=self.id, stock__gte=quantity
            ).update(stock=F("stock") - quantity)
            if updated_rows == 0:
                raise ValidationError(_("Số lượng hàng trong kho không đủ."))

        # Cập nhật lại instance với stock mới từ DB
        self.refresh_from_db(fields=["stock"])


class StockSetting(models.Model):
    variant = models.OneToOneField(
        Variant, on_delete=models.CASCADE, related_name="stock_setting"
    )
    safety_stock_threshold = models.PositiveIntegerField(default=0)  # Ngưỡng cảnh báo
    reminder_enabled = models.BooleanField(default=False)  # Bật/tắt cảnh báo

    def __str__(self):
        return _("Nhắc nhở kho cho sản phẩm %s - %s") % (
            self.variant.product.name,
            self.variant.name,
        )


class Gallery(models.Model):
    product = models.ForeignKey(
        "Product",
        verbose_name=_("Sản Phẩm"),
        on_delete=models.CASCADE,
        related_name="gallery",
    )
    image = CustomImageField(
        _("Hình Ảnh"),
        default="images/NoImage.png",
        max_size=2 * 1024 * 1024,
        max_resolution=(1280, 1280),
        upload_to=image_upload_to,
    )
    order = models.PositiveIntegerField(_("Thứ Tự"))
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Ảnh Sản Phẩm")
        verbose_name_plural = _("Ảnh Sản Phẩm")
        ordering = ["order"]

    def __str__(self):
        return f"[{self.product.name}] - Image"

    @display(description=_("Xem trước Hình ảnh"))
    def preview_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="64" height="64" />')
        return mark_safe(
            f'<img src="{settings.MEDIA_URL}{default_no_image}" width="64" height="64" />'
        )


class Promotion(models.Model):
    name = models.CharField(_("Tên Sự Kiện Khuyến Mãi"), max_length=250)
    start_date = models.DateTimeField(_("Thời Gian Bắt Đầu"), default=now)
    end_date = models.DateTimeField(_("Thời Gian Kết Thúc"), null=True, blank=True)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        verbose_name=_("Người Tạo"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.start_date.strftime('%d/%m/%Y %H:%M')} -> {self.end_date.strftime('%d/%m/%Y %H:%M')}"

    def clean(self):
        """Đảm bảo ngày kết thúc phải sau ngày bắt đầu"""
        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError(
                {"end_date": _("Thời gian kết thúc phải sau thời gian bắt đầu")}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PromotionItem(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("amount", "Giảm số tiền cố định"),
        ("percent", "Giảm theo %"),
    ]
    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, related_name="promotion_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="promotion_items"
    )
    variant = models.ForeignKey(
        Variant, on_delete=models.CASCADE, related_name="promotion_items"
    )
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(
        _("Giá Tiền Giảm"),
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(1)],
    )
    user_purchase_limit = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)

    class Meta:
        unique_together = (
            "promotion",
            "variant",
        )  # Không cho phép trùng variant trong cùng 1 chương trình

    def __str__(self):
        discount_str = (
            f"{number_format(self.discount_value, decimal_pos=decimal_places, use_l10n=False, force_grouping=True)}đ"
            if self.discount_type == "amount"
            else f"{self.discount_value}%"
        )
        return _(
            "{product} - {variant} - {promotion} Giảm {discount} ( Từ {start} đến {end} )"
        ).format(
            product=self.product.sku,
            variant=self.variant.name,
            promotion=self.promotion.name,
            discount=discount_str,
            start=localtime(self.promotion.start_date).strftime("%H:%M %d/%m/%Y"),
            end=localtime(self.promotion.end_date).strftime("%H:%M %d/%m/%Y"),
        )

    def clean(self):
        """Đảm bảo không có 2 khuyến mãi trùng thời gian cho cùng một variant"""
        existing_promotions = PromotionItem.objects.filter(
            product=self.product,
            variant=self.variant,
            promotion__start_date__lte=self.promotion.end_date,
            promotion__end_date__gte=self.promotion.start_date,
        ).exclude(id=self.id)

        if existing_promotions.exists():
            raise ValidationError(
                _("Sản phẩm này đã có khuyến mãi trong khoảng thời gian này.")
            )

        # Lấy giá gốc của variant
        original_price = self.variant.price

        # Kiểm tra giảm giá hợp lệ
        if self.discount_type == "amount":
            if self.discount_value >= original_price:
                raise ValidationError(
                    {"discount_value": _("Giá giảm phải nhỏ hơn giá gốc của sản phẩm.")}
                )
        elif self.discount_type == "percent":
            if not (1 <= self.discount_value <= 100):
                raise ValidationError(
                    {"discount_value": _("Phần trăm giảm không hợp lệ.")}
                )

    def save(self, *args, **kwargs):
        self.clean()
        # Thêm promotion vào product.promotions nếu chưa có
        if not self.product.promotions.filter(id=self.promotion.id).exists():
            self.product.promotions.add(self.promotion)
        super().save(*args, **kwargs)


class Cart(models.Model):
    user = models.OneToOneField(
        User, verbose_name=_("Tài Khoản"), on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Giỏ Hàng")
        verbose_name_plural = _("Giỏ Hàng")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Cart ({self.user if self.user else 'Session'})"

    def get_total_price(self):
        """Tính tổng giá trị giỏ hàng"""
        return sum(item.get_total_price() for item in self.cart_items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        verbose_name=_("Giỏ Hàng"),
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    product = models.ForeignKey(
        Product, verbose_name=_("Sản Phẩm"), on_delete=models.SET_NULL, null=True
    )
    variant = models.ForeignKey(
        Variant,
        verbose_name=_("Phân Loại"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField(_("Số Lượng"), default=0)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Giỏ Hàng")
        verbose_name_plural = _("Giỏ Hàng")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} - {self.variant} - Số Lượng: {self.quantity}"

    def get_total_price(self):
        """Tính tổng giá của sản phẩm trong giỏ hàng"""
        discount_price = getattr(
            self.variant, "discount_price", self.variant.price
        )  # Nếu không có discount_price thì lấy price
        return self.quantity * discount_price


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Chờ xử lý"),
        ("packaging", "Đóng gói"),
        ("shipped", "Đã vận chuyển"),
        ("delivered", "Đã giao"),
        ("return_requested", "Yêu cầu trả hàng"),
        ("return_approved", "Chấp nhận trả hàng"),
        ("return_rejected", "Từ chối trả hàng"),
        ("returned", "Đã trả hàng"),
        ("refund_processed", "Hoàn tiền"),
        ("canceled", "Đã hủy"),
    ]

    user = models.ForeignKey(
        User,
        verbose_name=_("Tài Khoản"),
        on_delete=models.CASCADE,
        related_name="orders",
    )
    invoice = CustomCharField(_("Mã Đơn Hàng"), max_length=15, unique=True)
    shipping_address = models.ForeignKey(
        "UserShippingAddress",
        verbose_name=_("Thông Tin Vận Chuyển"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    total_price = models.IntegerField(_("Tổng Tiền"), default=0)
    shipping_cost = models.IntegerField(_("Phí Ship"), default=0)
    status = models.CharField(
        _("Trạng Thái"), max_length=20, default="pending", choices=STATUS_CHOICES
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Đơn Hàng")
        verbose_name_plural = _("Đơn Hàng")
        ordering = ["-updated_at"]

    def __str__(self):
        return self.invoice

    @staticmethod
    def get_valid_transitions():
        return {
            "pending": ["packaging", "canceled"],
            "packaging": ["shipped", "canceled"],
            "shipped": ["delivered", "canceled"],
            "delivered": ["return_requested"],
            "return_requested": ["return_approved", "return_rejected"],
            "return_approved": ["returned"],
            "returned": ["refund_processed"],
            "refund_processed": [],  # Hoàn tất, không thể thay đổi
        }

    def is_valid_status_transition(self, old_status, new_status):
        if not self.pk or old_status == new_status:
            # Nếu là đơn hàng mới hoặc trạng thái không thay đổi thì không cần kiểm tra
            return True
        valid_transitions = self.get_valid_transitions()
        return new_status in valid_transitions.get(old_status, [])

    def get_absolute_url(self):
        return reverse("store:order_detail", kwargs={"invoice": self.invoice})

    def clean(self):

        if self.total_price < 0:
            raise ValidationError(
                {"total_price": _("Tổng giá trị đơn hàng không thể âm.")}
            )

        if self.status not in dict(self.STATUS_CHOICES):
            raise ValidationError({"status": _("Trạng thái đơn hàng không hợp lệ.")})

        if self.pk:  # Nếu đơn hàng đã tồn tại (không phải đơn mới)
            old_status = self.__class__.objects.get(pk=self.pk).status  # Trạng thái cũ
            new_status = self.status

            if not self.is_valid_status_transition(old_status, new_status):
                raise ValidationError(
                    {
                        "status": _("Không thể chuyển trạng thái từ '%s' sang '%s'.")
                        % (old_status, new_status)
                    }
                )

    def save(self, *args, **kwargs):
        self.clean()
        is_new = self.pk is None
        old_status = None if is_new else Order.objects.get(pk=self.pk).status
        new_status = self.status
        if is_new and not self.invoice:
            self.invoice = generate_unique_invoice(self)
        super().save(*args, **kwargs)

        if new_status == "delivered" and old_status != "delivered":
            for item in self.order_items.all():
                item.product.update_sales_count(
                    item.quantity
                )  # Cập nhật số lượng bán của sản phẩm
        if old_status and old_status != new_status:
            OrderStatusHistory.create_history(self, old_status)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name=_("Đơn Hàng"),
        on_delete=models.CASCADE,
        related_name="order_items",
    )
    image = models.ImageField(
        _("Hình Ảnh"), upload_to=image_upload_to, default="images/NoImage.png"
    )
    product = models.ForeignKey(
        Product, verbose_name=_("Sản Phẩm"), on_delete=models.SET_NULL, null=True
    )
    variant = models.ForeignKey(
        Variant,
        verbose_name=_("Phân Loại"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    name = models.CharField(_("Tên Sản Phẩm"), max_length=255, null=True, blank=True)
    attributes = models.CharField(
        _("Thuộc Tính"), max_length=255, blank=True, null=True
    )
    quantity = models.PositiveIntegerField(_("Số Lượng"), default=0)
    price = models.DecimalField(
        _("Giá Gốc"),
        default=0,
        max_digits=10,
        decimal_places=decimal_places,
        validators=[MaxValueValidator(9999999999)],
    )
    discount_price = models.DecimalField(
        _("Giá Khuyến Mãi"),
        default=0,
        max_digits=10,
        decimal_places=decimal_places,
        validators=[MaxValueValidator(9999999999)],
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    def __str__(self):
        return f"{self.order} - {self.name}"

    @property
    def get_total_price(self):
        return (
            self.quantity * self.discount_price
            if self.discount_price < self.price
            else self.quantity * self.price
        )

    def clean(self):
        if self.discount_price is not None and self.discount_price > self.price:
            raise ValidationError(
                {"discount_price": _("Giá khuyến mãi không thể cao hơn giá gốc.")}
            )

    def save(self, *args, **kwargs):
        self.clean()
        if self.pk:
            old_quantity = OrderItem.objects.get(pk=self.pk).quantity  # Lấy số lượng cũ
            quantity_diff = self.quantity - old_quantity  # Tính chênh lệch

            if quantity_diff > 0:  # Nếu số lượng mới lớn hơn -> giảm kho
                self.variant.update_stock(quantity_diff, increase=False)
            elif quantity_diff < 0:  # Nếu số lượng mới nhỏ hơn -> hoàn kho
                self.variant.update_stock(abs(quantity_diff), increase=True)
        else:
            # Nếu là tạo mới -> giảm kho theo số lượng
            self.variant.update_stock(self.quantity, increase=False)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Hoàn lại stock khi xóa OrderItem"""
        self.variant.update_stock(self.quantity, increase=True)
        super().delete(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name=_("Đơn Hàng"),
        related_name="order_status_history",
        on_delete=models.CASCADE,
    )
    previous_status = models.CharField(
        _("Trạng thái cũ"), max_length=20, null=True, blank=True
    )
    new_status = models.CharField(_("Trạng thái mới"), max_length=20)
    title = models.CharField(_("Tiêu Đề"), max_length=255)
    description = models.TextField(_("Nội Dung"), blank=True)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    created_by = models.ForeignKey(
        "User", verbose_name=_("Người Tạo"), on_delete=models.SET_NULL, null=True
    )

    def __str__(self):
        return f"{self.order} - {self.previous_status} ➝ {self.new_status} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"

    class Meta:
        verbose_name = _("Lịch Sử Trạng Thái Đơn Hàng")
        verbose_name_plural = _("Lịch Sử Trạng Thái Đơn Hàng")
        ordering = ["-created_at"]

    STATUS_MESSAGES = {
        "pending": {
            "title": "Đơn hàng đã được đặt.",
            "description": "Đặt hàng thành công.",
        },
        "packaging": {
            "title": "Đơn hàng đang được đóng gói",
            "description": "Chúng tôi đang chuẩn bị sản phẩm của bạn để giao hàng.",
        },
        "shipped": {
            "title": "Đơn hàng đang trên đường giao",
            "description": "Đơn hàng của bạn đã được giao cho đơn vị vận chuyển.",
        },
        "delivered": {
            "title": "Đơn hàng đã giao thành công",
            "description": "Bạn đã nhận được đơn hàng. Cảm ơn bạn đã mua sắm!",
        },
        "return_requested": {
            "title": "Yêu cầu trả hàng",
            "description": "Bạn đã yêu cầu trả hàng. Hệ thống đang xem xét yêu cầu của bạn.",
        },
        "return_approved": {
            "title": "Trả hàng được chấp nhận",
            "description": "Yêu cầu trả hàng của bạn đã được duyệt. Vui lòng gửi sản phẩm về kho.",
        },
        "return_rejected": {
            "title": "Yêu cầu trả hàng bị từ chối.",
            "description": "Yêu cầu trả hàng của bạn đã bị từ chối. Vui lòng liên hệ để biết thêm chi tiết.",
        },
        "returned": {
            "title": "Sản phẩm đã được trả về",
            "description": "Kho hàng đã nhận được sản phẩm trả về của bạn.",
        },
        "refund_processed": {
            "title": "Hoàn tiền thành công",
            "description": "Số tiền hoàn lại đã được xử lý. Vui lòng kiểm tra tài khoản ngân hàng của bạn.",
        },
        "canceled": {
            "title": "Đơn hàng đã bị hủy",
            "description": "Đơn hàng của bạn đã bị hủy. Nếu có bất kỳ thắc mắc nào, vui lòng liên hệ hỗ trợ.",
        },
    }

    @classmethod
    def create_history(cls, order, previous_status=None):
        """Tạo bản ghi lịch sử trạng thái với title và description"""
        new_status = order.status
        if new_status != "pending" and not previous_status:
            raise ValidationError(
                {"previous_status": _("Thiếu thông tin trạng thái trước đó")}
            )
        status_messages = cls.STATUS_MESSAGES
        message = status_messages.get(
            new_status, {"title": new_status, "description": ""}
        )
        cls.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            title=message["title"],
            description=message["description"],
        )

    def save(self, *args, **kwargs):
        """Tự động đặt title & description nếu chưa có"""
        if not self.title or not self.description:
            status_message = self.STATUS_MESSAGES.get(
                (self.previous_status, self.new_status),
                {
                    "title": "Cập nhật trạng thái",
                    "description": "Trạng thái đơn hàng đã thay đổi.",
                },
            )
            self.title = status_message["title"]
            self.description = status_message["description"]

        super().save(*args, **kwargs)


class ShippingInfo(models.Model):
    order = models.OneToOneField(
        Order,
        verbose_name=_("Đơn Hàng"),
        related_name="shipping_info",
        on_delete=models.CASCADE,
    )
    shipping_company = models.CharField(_("Đơn Vị Vận Chuyển"), max_length=100)
    tracking_number = models.CharField(
        _("Mã Vận Đơn"), max_length=100, blank=True, null=True
    )
    shipment_date = models.DateTimeField(_("Ngày Gửi"), null=True, blank=True)
    estimated_delivery = models.DateTimeField(
        _("Ngày Giao Dự Kiến"), null=True, blank=True
    )
    actual_delivery = models.DateTimeField(
        _("Ngày Giao Thực Tế"), null=True, blank=True
    )
    tracking_url = models.URLField(_("Đường Dẫn Tra Cứu"), null=True, blank=True)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    def __str__(self):
        return _("Thông Tin Vận Chuyển Của Đơn Hàng %s") % self.order.invoice

    class Meta:
        ordering = ["shipment_date"]


class City(models.Model):
    name = models.CharField(_("Tên"), max_length=100)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Tỉnh/Thành Phố")
        verbose_name_plural = _("Tỉnh/Thành Phố")

    def __str__(self):
        return self.name


class District(models.Model):
    city = models.ForeignKey(City, related_name="districts", on_delete=models.CASCADE)
    name = models.CharField(_("Tên"), max_length=100)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Quận/Huyện")
        verbose_name_plural = _("Quận/Huyện")

    def __str__(self):
        return self.name


class Ward(models.Model):
    district = models.ForeignKey(
        District, related_name="wards", on_delete=models.CASCADE
    )
    name = models.CharField(_("Tên"), max_length=100)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Phường/Xã")
        verbose_name_plural = _("Phường/Xã")

    def __str__(self):
        return self.name


class UserShippingAddress(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name=_("Tài Khoản"),
        on_delete=models.CASCADE,
        related_name="shipping_addresses",
    )
    full_name = models.CharField(_("Người Nhận"), max_length=255)
    phone_number = models.CharField(
        _("Điện Thoại"),
        max_length=20,
        validators=[phone_number_validator],
    )
    street_address = models.CharField(_("Địa Chỉ"), max_length=512)
    city = models.ForeignKey(
        City, verbose_name=_("Tỉnh/Thành Phố"), on_delete=models.SET_NULL, null=True
    )
    district = models.ForeignKey(
        District, verbose_name=_("Quận/Huyện"), on_delete=models.SET_NULL, null=True
    )
    ward = models.ForeignKey(
        Ward, verbose_name=_("Phường/Xã"), on_delete=models.SET_NULL, null=True
    )
    postal_code = models.CharField(
        _("Mã Bưu Điện"), max_length=10, blank=True, null=True
    )
    is_default = models.BooleanField(_("Mặc Định"), default=False)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)

    class Meta:
        verbose_name = _("Địa Chỉ Giao Hàng")
        verbose_name_plural = _("Địa Chỉ Giao Hàng")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.street_address}, {self.ward}, {self.district}, {self.city}"

    @property
    def get_full_address(self):
        """
        Trả về địa chỉ đầy đủ.
        """
        address_parts = [
            self.street_address,
            self.ward.name if self.ward else None,
            self.district.name if self.district else None,
            self.city.name if self.city else None,
        ]
        full_address = ", ".join(filter(None, address_parts))  # Loại bỏ phần None/null
        return full_address

    def clean(self):
        """Kiểm tra số lượng địa chỉ tối đa trước khi lưu"""
        if self.user.shipping_addresses.count() >= 3 and not self.pk:
            raise ValidationError(
                "Mỗi người dùng chỉ có thể có tối đa 3 địa chỉ giao hàng."
            )

    def save(self, *args, **kwargs):
        self.clean()
        """ Đảm bảo chỉ có 1 địa chỉ mặc định """
        if self.is_default:
            UserShippingAddress.objects.filter(user=self.user).update(is_default=False)

        super().save(*args, **kwargs)


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Chưa thanh toán"),
        ("paid", "Đã thanh toán"),
        ("failed", "Thất bại"),
    ]

    PAYMENT_METHODS = [
        ("cod", "COD"),
        ("momo", "Momo"),
        ("paypal", "PayPal"),
    ]

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="payment", null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(
        max_length=100, blank=True, null=True, unique=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Thanh Toán")
        verbose_name_plural = _("Thanh Toán")

    def __str__(self):
        return f"Payment {self.id} - {self.order.invoice} - {self.status}"

    def clean(self):
        print(self.amount)
        if self.amount <= 0:
            raise ValidationError({"amount": _("Số tiền thanh toán phải lớn hơn 0.")})

        if self.payment_method != "cod" and not self.transaction_id:
            raise ValidationError(
                {"transaction_id": _("Cổng thanh toán yêu cầu transaction_id hợp lệ.")}
            )

        if self.payment_method not in dict(
            self._meta.get_field("payment_method").choices
        ):
            raise ValidationError(
                {"payment_method": _("Phương thức thanh toán không hợp lệ.")}
            )

        if self.status not in dict(self._meta.get_field("status").choices):
            raise ValidationError({"status": _("Trạng Thái thanh toán không hợp lệ.")})

        if self.status == "paid" and not self.paid_at:
            self.paid_at = now()()
        elif self.status != "paid" and self.paid_at:
            raise ValidationError(
                {
                    "paid_at": _(
                        "Chỉ có thể đặt thời gian thanh toán nếu đơn hàng đã thanh toán."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Review(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name=_("Sản Phẩm"),
        related_name="reviews",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User, verbose_name=_("Tài Khoản"), on_delete=models.CASCADE
    )
    score = models.PositiveSmallIntegerField(
        _("Điểm"), choices=[(i, i) for i in range(1, 6)]
    )
    comment = models.OneToOneField(
        "Comment",
        verbose_name=_("Bình Luận"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="review",
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Đánh Giá")
        verbose_name_plural = _("Đánh Giá")

    def __str__(self):
        return "%s đánh giá %d★ sản phẩm %s " % (
            self.user.full_name,
            self.score,
            self.product,
        )

    @property
    def timesince(self):
        return _("%s trước") % timesince.timesince(self.created_at)


class Comment(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name=_("Sản Phẩm"),
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        User, verbose_name=_("Tài Khoản"), on_delete=models.CASCADE
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Bình Luận Cha"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    content = CustomTextField(
        _("Nội Dung"),
        null=True,
        blank=True,
        validators=[
            # MinLengthValidator(10, message="Nội dung phải có ít nhất 10 ký tự."),
            MaxLengthValidator(
                1000, message=_("Nội dung không được vượt quá 1000 ký tự.")
            )
        ],
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Bình Luận")
        verbose_name_plural = _("Bình Luận")
        ordering = ["-created_at"]

    def __str__(self):
        return (
            _("Trả lời bình luận %s") % self.parent
            if self.parent
            else _("%s bình luận sản phẩm %s") % (self.user.full_name, self.product)
        )

    @property
    def timesince(self):
        return _("%s trước") % timesince.timesince(self.created_at)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Notification(models.Model):
    # Các loại thông báo
    NOTIFICATION_TYPES = [
        ("ORDER_STATUS", _("Trạng thái đơn hàng")),
        ("COMMENT", _("Bình luận")),
        ("ACCOUNT", _("Tài khoản")),
        ("SYSTEM", _("Hệ thống")),
        ("PROMOTION", _("Khuyến mãi")),
        ("GENERAL", _("Thông báo chung")),
    ]

    # Danh sách loại thông báo cần lọc
    FILTER_TYPES = ["PROMOTION", "GENERAL", "SYSTEM"]

    user = models.ForeignKey(
        User,
        verbose_name=_("Tài Khoản"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )  # Người nhận thông báo
    image = CustomImageField(
        _("Hình Ảnh"), upload_to=notification_image_upload_to, null=True, blank=True
    )  # Hình ảnh sản phẩm hoặc hình ảnh khuyến mãi
    title = models.CharField(_("Tiêu Đề"), max_length=255)
    message = models.TextField(_("Nội Dung"))  # Nội dung thông báo
    notification_type = models.CharField(
        _("Loại Thông Báo"),
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default="GENERAL",
    )  # Loại thông báo
    link = models.URLField(
        _("Liên Kết"), null=True, blank=True
    )  # Đường dẫn đến chi tiết đơn hàng, khuyến mãi, v.v.
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    def __str__(self):
        return f"{self.user.full_name if self.user else 'GENERAL'} - {self.title}"

    class Meta:
        verbose_name = _("Thông Báo")
        verbose_name_plural = _("Thông Báo")
        ordering = ["-updated_at"]

    @property
    def timesince(self):
        return _("%s ago") % timesince.timesince(self.updated_at)


class NotificationRead(models.Model):
    user = models.ForeignKey(
        User, verbose_name=_("Tài Khoản"), on_delete=models.CASCADE
    )
    notification = models.ForeignKey(
        Notification,
        verbose_name=_("Thông Báo"),
        on_delete=models.CASCADE,
        related_name="notification_read",
    )
    is_read = models.BooleanField(_("Đã Đọc"), default=False)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Thông Báo Đã Đọc")
        verbose_name_plural = _("Thông Báo Đã Đọc")
        unique_together = ["user", "notification"]

    def __str__(self):
        return f"{self.user.email} - Notification: {self.notification.title} - Read: {self.is_read}"


class NotificationSettings(models.Model):
    user = models.OneToOneField(
        User,
        verbose_name=_("Tài Khoản"),
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )
    email_notification = models.BooleanField(_("Thông Báo qua email"), default=True)
    sms_notification = models.BooleanField(_("Thông Báo qua tin Nhắn"), default=True)
    promotion_email = models.BooleanField(_("Khuyến Mãi qua email"), default=True)
    promotion_sms = models.BooleanField(_("Khuyến Mãi qua tin Nhắn"), default=True)
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Cài Đặt Thông Báo")
        verbose_name_plural = _("Cài Đặt Thông Báo")

    def __str__(self):
        return f"Cài Đặt Thông cho {self.user.full_name}"


class Wishlist(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name=_("Tài Khoản"),
        on_delete=models.CASCADE,
        related_name="wishlist",
    )
    product = models.ForeignKey(
        Product, verbose_name=_("Sản Phẩm"), on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        Variant, verbose_name=("Phân Loại"), on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(_("Ngày Tạo"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ngày Cập Nhật"), auto_now=True)

    class Meta:
        verbose_name = _("Yêu Thích")
        verbose_name_plural = _("Yêu Thích")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "variant"],
                name="unique_user_variant",
                violation_error_message=_(
                    "Sản phẩm này đã có trong danh sách yêu thích của bạn."
                ),
            ),
        ]

    # def validate_unique(self,exclude=None):
    #     try:
    #         super().validate_unique()
    #     except ValidationError as e:
    #         raise ValidationError(_('Sản phẩm này đã có trong danh sách yêu thích của bạn.'))

    def __str__(self):
        return f"{self.user.full_name} - {self.product} {self.variant.name if self.variant.name else '' }"


class ChatUser(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="chat_user"
    )  # Người dùng đăng nhập
    guest_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # Người dùng không đăng nhập
    name = models.CharField(max_length=255, blank=False, null=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.full_name if self.user else self.name}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.user and not self.guest_id:
            self.guest_id = get_random_string(16)
        super().save(*args, **kwargs)


class ChatRoom(models.Model):
    WAITING = "waiting"
    ACTIVE = "active"
    CLOSED = "closed"
    CHOICES_STATUS = (
        (WAITING, "Chờ Tiếp Nhận"),
        (ACTIVE, "Đã Tiếp Nhận"),
        (CLOSED, "Đóng"),
    )
    name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    recipient = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=CHOICES_STATUS, default=WAITING)
    created_by = models.ForeignKey(ChatUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Room: {self.name} - Created At: {self.created_at}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.name:
            self.name = get_random_string(8)
        super().save(*args, **kwargs)


class ChatMessage(models.Model):
    chat_room = models.ForeignKey(
        ChatRoom, related_name="messages", on_delete=models.CASCADE
    )
    content = models.TextField()
    sender = models.ForeignKey(ChatUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.name }: {self.content[:50]} - {self.created_at}"
