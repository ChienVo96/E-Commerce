from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt import token_blacklist


class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('preview_avatar','full_name','email','phone_number','is_active','is_staff','is_vendor','last_login')
    ordering = ['email']
    list_filter = ('is_active','is_staff','is_vendor',)
    fieldsets = (
        (None, {'fields': ('preview_avatar','avatar','email', 'phone_number', 'password')}),
        ('Personal info', {'fields': ('full_name', 'birth','address')}),
        ('Vendor info', {'fields': ('is_vendor',)}),  # Added field
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'user_permissions', 'groups')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    readonly_fields = ('created_at','preview_avatar')
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name','password1', 'password2'),
        }),
    )
    add_form_template = 'admin/auth/user/add_form.html'
    
    class Media:
        js = ('js/admin/image_preview.js',)
    
class SubCategoryInline(admin.TabularInline):
    model = Category
    fields = ['image','name','is_active']
    ordering = ['created_at']
    extra = 0
    
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['preview_image','name','is_active']
    fields = ['preview_image','image','parent','name','slug','is_active','created_at','updated_at']
    readonly_fields = ['preview_image','created_at','updated_at'] 
    inlines = [SubCategoryInline,]
    
    class Media:
        js = ('js/admin/image_preview.js',)
    
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

class CartAdmin(admin.ModelAdmin):
    list_display= ['user','created_at']
    inlines = [CartItemInline,]
    
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ['product','quantity','price']
    extra = 0
    
class OrderAdmin(admin.ModelAdmin):
    list_display = ['invoice','user','total_price','get_status_display','status','created_at']
    inlines = [OrderItemInline,]
    
    @display(description=_('Thanh Toán'))
    def get_status_display(self, obj):
        return obj.payment.get_status_display()  
    
class GalleryInLine(admin.TabularInline):
    model = Gallery
    fields = ['preview_image','image','order']
    readonly_fields = ('preview_image',)
    extra = 0
    
class GalleryAdmin(admin.ModelAdmin):
    list_display = ['preview_image','product']
    fields = ['preview_image','image','product','order']
    readonly_fields = ['preview_image'] 
    
    class Media:
        js = ('js/admin/image_preview.js',)
    
class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    fields = ['name']
    extra = 0
            
class VariantInline(admin.TabularInline):
    model = Variant
    fields = ['preview_image','price','stock']
    readonly_fields = ['preview_image']
    extra = 0
    
class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    fields = ['preview_image','image','value']
    readonly_fields = ['preview_image'] 
    extra = 0
    
class ProductAttributeAdmin(admin.ModelAdmin):
    fields = ['product','name']
    inlines = [AttributeValueInline]
    
    class Media:
        js = ('js/admin/image_preview.js',)
    
class ProductAdmin(admin.ModelAdmin):
    list_display = ['preview_image','sku','name','category','is_active']
    fields = ['sku','name','slug','category','description','sale_count','view_count','search_count','detail','promotions','is_active']
    readonly_fields = ('sale_count','view_count', 'search_count',)
    inlines = [GalleryInLine,ProductAttributeInline,VariantInline]
    filter_horizontal = ['promotions',]
    class Media:
        js = ('js/admin/image_preview.js',)
        
class VariantAdmin(admin.ModelAdmin):
    fields = ['preview_image','product','sku','name','price','stock','attribute_values','is_default']
    readonly_fields = ['preview_image'] 
    
    class Media:
        js = ('js/admin/image_preview.js',)
    
class WardInLine(admin.TabularInline):
    model = Ward
    fields = ['name']
    extra = 0

class DistrictAdmin(admin.ModelAdmin):
    fields = ['name']
    inlines = [WardInLine]
    
class DistrictInLine(admin.TabularInline):
    model = District
    fields = ['name']
    extra = 0
    
class CityAdmin(admin.ModelAdmin):
    fields = ['name']
    inlines = [DistrictInLine]
    
class OutstandingTokenAdmin(token_blacklist.admin.OutstandingTokenAdmin):
    actions = []  # Đăng ký hành động xóa

    def has_delete_permission(self, request, obj=None):
        """
        Xác định xem người dùng có quyền xóa hay không.
        """
        return True  # Hoặc logic tùy chỉnh của bạn
    
admin.site.register(User, UserAdmin)
admin.site.register(Category,CategoryAdmin)
admin.site.register(Product,ProductAdmin)
admin.site.register(Variant,VariantAdmin)
admin.site.register(StockSetting)
admin.site.register(Gallery,GalleryAdmin)
admin.site.register(ProductAttribute,ProductAttributeAdmin)
admin.site.register(AttributeValue)

admin.site.register(Cart,CartAdmin)
admin.site.register(OrderStatusHistory)
admin.site.register(Order,OrderAdmin)
admin.site.register(OrderItem)
admin.site.register(Promotion)
admin.site.register(PromotionItem)
admin.site.register(Payment)
admin.site.register(UserShippingAddress)
admin.site.register(Review)
admin.site.register(Comment)
admin.site.register(City,CityAdmin)
admin.site.register(District,DistrictAdmin)
admin.site.register(Ward)
admin.site.register(NotificationSettings)
admin.site.register(Notification)
admin.site.register(NotificationRead)
admin.site.register(Wishlist)
admin.site.register(ChatUser)
admin.site.register(ChatRoom)
admin.site.register(ChatMessage)
admin.site.unregister(token_blacklist.models.OutstandingToken)
admin.site.register(token_blacklist.models.OutstandingToken, OutstandingTokenAdmin)




