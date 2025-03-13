from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from . import views
from .serializers import TokenObtainSerializer

app_name = "api"
urlpatterns = [
    # Token endpoints
    path(
        "token/",
        TokenObtainPairView.as_view(serializer_class=TokenObtainSerializer),
        name="token_obtain_pair",
    ),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    # Districts and Wards
    path("district/<int:city_id>/", views.get_districts, name="get-district"),
    path("ward/<int:district_id>/", views.get_wards, name="get-ward"),
    # User
    path("users/", views.UserListCreateAPIView.as_view(), name="user-list-create"),
    path(
        "users/<int:pk>/",
        views.UserRetrieveUpdateDestroyAPIView.as_view(),
        name="user-retrieve-update-destroy",
    ),
    path('users/bulk-delete/', views.BulkDeleteUserAPIView.as_view(), name='user-bulk-delete'),
    path(
        "users/<int:pk>/password-change/",
        views.PasswordChangeAPIView.as_view(),
        name="password_change",
    ),
    path(
        "forget-password/",
        views.ForgetPasswordAPIView.as_view(),
        name="forget-password",
    ),
    path(
        "reset-password/", views.PasswordResetAPIView.as_view(), name="reset-password"
    ),
    # Shipping address actions
    path(
        "shipping-address/",
        views.ShippingAddressView.as_view(),
        name="shipping_address_list_create",
    ),
    path(
        "shipping-address/<int:pk>/",
        views.ShippingAddressView.as_view(),
        name="shipping_address_read_update_delete",
    ),
    # Notification settings
    path(
        "notification-settings/",
        views.NotificationSettingsView.as_view(),
        name="notification_settings",
    ),
    path(
        "notification-settings/<int:pk>/",
        views.NotificationSettingsView.as_view(),
        name="notification_settings",
    ),
    # Category
    path("categories/", views.CategoryAPIView.as_view(), name="category-list-create"),  #
    path(
        "categories/<int:pk>/",
        views.CategoryAPIView.as_view(),
        name="category-read-update-delete",
    ),
    path(
        "categories/bulk-delete/",
        views.CategoryBulkDeleteView.as_view(),
        name="category-bulk-delete",
    ),
    path(
        "categories/import/", views.CategoryImportView.as_view(), name="category-import"
    ),
    path(
        "categories/export/", views.CategoryExportView.as_view(), name="category-export"
    ),
    # Product
    path("products/", views.ProductListAPIView.as_view(), name="product-list"),
    path("products/public/", views.ProductListPublicAPIView.as_view(), name="product-list-public"),
    path("products/create/", views.ProductAPIView.as_view(), name="product-create"),
    path(
        "products/<int:pk>/",
        views.ProductAPIView.as_view(),
        name="product-read-update-delete",
    ),
    path(
        "products/<int:pk>/reviews/",
        views.ProductReviewAPIView.as_view(),
        name="product-reviews-list-create",
    ),
    path(
        "products/<int:pk>/reviews/summary/",
        views.ProductReviewSummaryAPIView.as_view(),
        name="product-reviews-summary",
    ),
    path(
        "products/<int:pk>/comments/",
        views.ProductCommentAPIView.as_view(),
        name="product-comments-list-create",
    ),
    path(
        "products/bulk-delete/",
        views.ProductBulkDeleteAPIView.as_view(),
        name="product-bulk-delete",
    ),
    #Variant
    path(
        "variants/",
        views.VariantListAPIView.as_view(),
        name="variant-list",
    ),
    # Promotion
    path('promotions/', views.PromotionAPIView.as_view(), name='promotion-list'),
    path('promotions/<int:pk>/', views.PromotionAPIView.as_view(), name='promotion-detail'),
    # Notifications
    path(
        "notifications/<int:pk>/mark-read/",
        views.NotificationMarkReadAPIView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/mark-read/",
        views.NotificationMarkReadAPIView.as_view(),
        name="notification-mark-all-read",
    ),
    # Wishlist
    path("wishlist/", views.WishlistAPIView.as_view(), name="wishlist_list_create"),
    path(
        "wishlist/<int:pk>/",
        views.WishlistAPIView.as_view(),
        name="wishlist_read_update_delete",
    ),
    # Cart
    path("cart/", views.CartView.as_view(), name="cart_detail"),
    path(
        "cart/item/",
        views.CartItemView.as_view(),
        name="cart_item_create",
    ),
    path(
        "cart/item/<int:pk>/",
        views.CartItemView.as_view(),
        name="cart_item_update_delete",
    ),
    # Order
    path("place-order/", views.PlaceOrderView.as_view(), name="place_order"),
    path("orders/create/", views.PlaceOrderView.as_view(), name="order_create"),
    path("chat-user/", views.ChatUserAPIView.as_view(), name="chat_user_create"),
    path("chat/", views.ChatRoomAPIView.as_view(), name="chat_room_create"),
    path("chat/<str:pk>/", views.ChatRoomAPIView.as_view(), name="chat_room"),
]
