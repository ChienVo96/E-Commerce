from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('dashboard/',views.DashboardView.as_view(),name='dashboard'),
    path('chats/',views.ChatListView.as_view(),name='chat_list'),
    path('chats/<int:pk>/',views.ChatDetailView.as_view(),name='chat_detail'),
    path('categories/',views.CategoryListView.as_view(),name='category_list'),
    path('products/',views.ProductListView.as_view(),name='product_list'),
    path('products/create/', views.ProductCreateUpdateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductCreateUpdateView.as_view(), name='product_update'),
    path('users/',views.UserListView.as_view(),name='user_list'),
    path('orders/',views.OrderListView.as_view(),name='order_list'),
    path('orders/<int:pk>/',views.OrderCreateUpdateView.as_view(),name='order_update'),
    path('orders/create/',views.OrderCreateUpdateView.as_view(),name='order_create'),
    path('promotions/',views.PromotionListView.as_view(),name='promotion_list'),
    path('promotions/<int:pk>/',views.PromotionCreateUpdateView.as_view(),name='promotion_update'),
    path('promotions/create/',views.PromotionCreateUpdateView.as_view(),name='promotion_create'),
    
    
    
]
