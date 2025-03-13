from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.db.models import (
    F,
    Value,
    Case,
    When,
    Subquery,
    OuterRef,
    DecimalField,
    CharField,
    Exists,
    FloatField,
    ExpressionWrapper,
)
from django.db.models.functions import Coalesce, Concat
from django.utils.timezone import now


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class VariantManager(models.Manager):
    def with_info_display(self):
        """Lấy thông tin hiển thị của variant bao gồm giá sau giảm giá, phần trăm giảm giá và ảnh"""
        from core.models import Variant

        return self.annotate(
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
            image=Subquery(
                Variant.objects.filter(
                    id=OuterRef("id"),
                    attribute_values__image__isnull=False,
                ).values("attribute_values__image")[:1]
            ),
        )
