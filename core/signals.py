import os
import shutil
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save, post_save, m2m_changed
from django.db.models import (
    Prefetch,
    OuterRef,
    Subquery,
    Case,
    When,
    Count,
    Value,
    F,
    ExpressionWrapper,
    DecimalField,
    IntegerField,
)
from django.urls import reverse
from django.utils.timesince import timesince
from django.utils.timezone import now
from api.serializers import CartSerializer
from .models import (
    AttributeValue,
    Cart,
    CartItem,
    ChatUser,
    Gallery,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    Review,
    User,
    Category,
    NotificationSettings,
    Comment,
    Variant,
)
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.core.files import File
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def delete_old_image_on_change(instance, field_name):
    if instance.pk:
        model = instance._meta.model
        default_path = (
            os.path.join(settings.MEDIA_ROOT, "images", "NoAvatar.png")
            if model.__name__ == "User"
            else os.path.join(settings.MEDIA_ROOT, "images", "NoImage.png")
        )
        try:
            # Get the old image
            old_image = getattr(model.objects.get(pk=instance.pk), field_name)

            # Get the new image from the instance
            new_image = getattr(instance, field_name)
            
            # Check if new image is different from old image and if old image exists
            if (
                old_image
                and new_image != old_image
                and os.path.isfile(old_image.path)
                and old_image.path != default_path
            ):
                # Delete the old image file
                print("Delete old image file:", old_image)
                old_image.delete(save=False)

        except Exception:
            return False


def delete_folder_image_on_delete(instance, field_name):
    if instance.pk:
        model = instance._meta.model
        # Get the image from the instance
        image = getattr(instance, field_name, None)
        default_path = (
            os.path.join(settings.MEDIA_ROOT, "images", "NoAvatar.png")
            if model.__name__ == "User"
            else os.path.join(settings.MEDIA_ROOT, "images", "NoImage.png")
        )

        if image and image.path != default_path and hasattr(image, "path"):
            path = os.path.dirname(image.path)

            # Check if the folder exists
            if os.path.exists(path):
                # Delete the folder and all its contents
                try:
                    shutil.rmtree(path)
                    print(f"Successfully deleted '{path}' and all its contents.")
                except Exception as e:
                    print(f"Error occurred while deleting folder: {e}")
            else:
                print(f"Folder '{path}' does not exist.")


def delete_image_on_delete(instance, field_name):
    """
    Xóa tệp hình ảnh liên kết với một trường ImageField khi đối tượng bị xóa.

    Args:
        instance: Đối tượng Django model chứa trường ImageField/FileField.
        field_name: Tên của trường ImageField/FileField.
    """
    if instance.pk:  # Đảm bảo đối tượng đã được lưu
        model = instance._meta.model
        # Lấy trường hình ảnh từ đối tượng
        image = getattr(instance, field_name, None)
        default_path = (
            os.path.join(settings.MEDIA_ROOT, "images", "NoAvatar.png")
            if model.__name__ == "User"
            else os.path.join(settings.MEDIA_ROOT, "images", "NoImage.png")
        )

        try:
            # Kiểm tra file có tồn tại và không phải ảnh mặc định
            if image and image.path != default_path and os.path.isfile(image.path):
                image.delete(save=False)
        except Exception as e:
            # Trường hợp đối tượng hoặc file không tồn tại
            print(f"Error deleting image: {e}")


@receiver(pre_save, sender=Gallery)
def delete_old_image_gallery_on_change(sender, instance, **kwargs):
    delete_old_image_on_change(instance, "image")


@receiver(post_delete, sender=Gallery)
def delete_image_gallery_on_delete(sender, instance, **kwargs):
    delete_image_on_delete(instance, "image")

@receiver(m2m_changed, sender=Variant.attribute_values.through)
def update_variant_name_on_m2m_change(sender, instance, action, **kwargs):
    """
    Khi thêm, sửa hoặc xóa attribute_values trong Variant, cập nhật lại tên Variant.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.update_name()
        
@receiver(post_save, sender=AttributeValue)
def update_variant_name_on_attr_value_change(sender, instance, **kwargs):
    """
    Khi giá trị AttributeValue thay đổi, cập nhật lại tên của tất cả các Variants chứa nó.
    """
    for variant in instance.variants.all():
        variant.update_name()
        
@receiver(pre_save, sender=AttributeValue)
def delete_old_image_attribute_value_on_change(sender, instance, **kwargs):
    delete_old_image_on_change(instance, "image")


@receiver(post_delete, sender=AttributeValue)
def delete_image_attribute_value_on_delete(sender, instance, **kwargs):
    delete_image_on_delete(instance, "image")


@receiver(pre_save, sender=User)
def delete_old_image_user_on_change(sender, instance, **kwargs):
    delete_old_image_on_change(instance, "avatar")


@receiver(post_delete, sender=User)
def delete_folder_image_user_on_delete(sender, instance, **kwargs):
    delete_folder_image_on_delete(instance, "avatar")


@receiver(post_save, sender=User)
def create_chat_and_notification_settings(sender, instance, created, **kwargs):
    # Khi một User mới được tạo, tạo NotificationSettings mặc định cho người đó
    if created:
        NotificationSettings.objects.create(
            user=instance,
            email_notification=True,
            sms_notification=True,
            promotion_email=True,
            promotion_sms=True,
        )
        ChatUser.objects.create(
            user=instance,
            name=instance.full_name,
            phone_number=instance.phone_number,
            email=instance.email,
        )


@receiver(pre_save, sender=Category)
def delete_old_image_category_on_change(sender, instance, **kwargs):
    delete_old_image_on_change(instance, "image")


@receiver(post_delete, sender=Category)
def delete_image_category_on_delete(sender, instance, **kwargs):
    try:
        # Kiểm tra nếu là Category cha (parent là None)
        if instance.parent is None:
            # Nếu là Category cha, gọi hàm xóa hình ảnh
            delete_folder_image_on_delete(instance, "image")

    except ObjectDoesNotExist:
        # Xử lý nếu Category không tồn tại
        print(f"Category {instance.id} đã bị xóa hoặc không tồn tại")


@receiver(post_delete, sender=Order)
def delete_related_order_and_folder_image_on_delete(sender, instance, **kwargs):
    notifications = Notification.objects.filter(
        user=instance.user, notification_type="ORDER_STATUS"
    )
    if notifications.exists():
        notifications.delete()
    folder_path = os.path.join(
        settings.MEDIA_ROOT, "images", "order", instance.invoice.lower()
    )
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        try:
            shutil.rmtree(folder_path)  # Xóa toàn bộ thư mục và các file bên trong
            print(f"Deleted folder: {folder_path}")
        except Exception as e:
            print(f"Error deleting folder {folder_path}: {e}")


@receiver(post_delete, sender=OrderItem)
def delete_image_order_item_on_delete(sender, instance, **kwargs):
    delete_image_on_delete(instance, "image")


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def clear_category_cache(sender, **kwargs):
    """Xóa cache khi danh mục thay đổi."""
    cache.delete("category_list")


@receiver(post_delete, sender=Review)
def delete_comment_on_rating_delete(sender, instance, **kwargs):
    """
    Xóa Comment liên kết khi Review bị xóa, nhưng kiểm tra sự tồn tại của Comment trước.
    """
    try:
        if instance.comment:
            # Kiểm tra và xóa comment nếu nó còn tồn tại
            instance.comment.delete()
    except ObjectDoesNotExist:
        # Nếu Comment không tồn tại thì bỏ qua
        pass


@receiver(post_save, sender=Comment)
def notify_comment_reply(sender, instance, created, **kwargs):
    if created and instance.parent:  # Chỉ gửi thông báo khi là reply
        parent_comment = instance.parent
        product = instance.product
        reply_user = instance.user
        comment_user = parent_comment.user
        if comment_user != reply_user:  # Không gửi thông báo nếu tự trả lời
            # Key cache để gộp thông báo
            notification_count_key = (
                f"notification_{comment_user.id}_{parent_comment.id}"
            )
            notification_count = cache.get(notification_count_key, 0)
            comment_or_review = (
                "đánh giá" if getattr(parent_comment, "rating", None) else "bình luận"
            )
            link = (
                f"/product/{product.slug}/?review-id={parent_comment.id}"
                if getattr(parent_comment, "rating", None)
                else f"/product/{product.slug}/?comment-id={parent_comment.id}"
            )

            # Đường dẫn đến hình ảnh
            image_path = os.path.join(
                settings.MEDIA_ROOT, "images/icons/message-bubble.png"
            )

            # Biến lưu thông tin chung để gửi qua WebSocket
            title = None
            message = None
            notification = (
                Notification.objects.filter(user=comment_user, link=link)
                .order_by("-created_at")
                .first()
            )
            if not notification or (
                notification and notification.notification_read.exists()
            ):
                # Nếu chưa có thông báo hoặc có thông báo nhưng đã đọc, tạo thông báo mới
                title = "Có trả lời mới cho %s của bạn" % comment_or_review
                message = "%s đã trả lời %s của bạn về sản phẩm %s." % (
                    reply_user.full_name,
                    comment_or_review,
                    parent_comment.product.name,
                )

                # Mở hình ảnh và lưu vào model Notification
                with open(image_path, "rb") as img_file:
                    img = File(img_file)

                    # Tạo thông báo với hình ảnh
                    if not notification:
                        notification = Notification.objects.create(
                            user=comment_user,
                            title=title,
                            message=message,
                            notification_type="COMMENT",
                            image=img,  # Lưu hình ảnh vào trường image (ImageField)
                            link=link,
                        )
                    else:
                        # Cập nhật lại thông báo
                        notification.title = title
                        notification.message = message
                        notification.save()
                # Lưu vào cache
                cache.set(notification_count_key, 1, timeout=600)  # Timeout 10 phút
            else:
                title = "Có nhiều trả lời mới cho %s của bạn" % comment_or_review
                message = "Bạn có %d trả lời mới cho %s của mình về sản phẩm %s." % (
                    notification_count + 1,
                    comment_or_review,
                    parent_comment.product.name,
                )

                # Cập nhật thông báo gộp
                notification.title = title
                notification.message = message
                notification.save()  # Lưu thông báo gộp đã được cập nhật

                # Cập nhật số lượng trả lời mới
                cache.set(notification_count_key, notification_count + 1, timeout=600)

            # Gửi thông báo qua WebSocket
            if notification:
                channel_layer = get_channel_layer()
                group_name = f"user_{comment_user.id}_notification"
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "send_notification",
                        "data": {
                            "id": notification.id,
                            "image": notification.image.url,
                            "link": link,
                            "title": title,
                            "message": message,
                            "timesince": instance.timesince,
                        },
                    },
                )


@receiver([post_save, post_delete], sender=CartItem)
def send_cart_update(sender, instance, **kwargs):
    """
    Gửi thông báo WebSocket khi giỏ hàng thay đổi.
    """
    user = instance.cart.user
    if not user:
        return

    variant_queryset = Variant.objects.annotate(
        image=Subquery(
            AttributeValue.objects.filter(
                variants=OuterRef("id"), image__isnull=False
            ).values("image")[
                :1
            ]  # Lấy ảnh của thuộc tính nếu có
        ),
        discount_price=Case(
            When(
                promotion_items__promotion__start_date__lte=now(),
                promotion_items__promotion__end_date__gte=now(),
                promotion_items__discount_type="percent",
                then=ExpressionWrapper(
                    F("price") * (1 - F("promotion_items__discount_value") / 100),
                    output_field=DecimalField(max_digits=10, decimal_places=0),
                ),
            ),
            When(
                promotion_items__promotion__start_date__lte=now(),
                promotion_items__promotion__end_date__gte=now(),
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

    if not cart_queryset:
        return

    # Serialize lại giỏ hàng (đã được optimize)
    cart_data = CartSerializer(cart_queryset).data

    # Tên nhóm WebSocket của user
    group_name = f"user_{user.id}_cart"

    # Gửi thông báo WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name, {"type": "send_cart_update", "cart": cart_data}
    )


@receiver(post_save, sender=OrderStatusHistory)
def send_order_status_notification(sender, instance, created, **kwargs):
    if created: 
        order = instance.order
        user = order.user
        title = f"Đơn hàng {order.invoice}"
        message = instance.description
        link = reverse("store:order_detail", kwargs={"invoice": order.invoice})
        image = order.order_items.first().image if order.order_items.exists() else None
        # Tạo thông báo cho user
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type="ORDER_STATUS",
            image=image,
            link=link
        )
        # Gửi thông báo qua WebSocket
        channel_layer = get_channel_layer()
        group_name = f"user_{user.id}_notification"

        notification_data = {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type,
            "image": notification.image.url if notification.image else None,
            "link": notification.link,
            "timesince": _("%s trước") % timesince(notification.created_at)
        }

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "data": notification_data,
            }
        )