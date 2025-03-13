from .models import User,Product,Category,Gallery,Order,OrderItem,AttributeValue,Variant,ProductAttribute
from django.forms.models import inlineformset_factory
from django import forms
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number', 'birth', 'gender']
        
class CustomVariantFormSet(forms.BaseInlineFormSet):

    def get_form_kwargs(self,index):
        kwargs = super().get_form_kwargs(index)
        kwargs['product'] = self.instance
        return kwargs

class BaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field.required:
                field_label = field.label or field_name
                field.error_messages['required'] = _('%s không được để trống.') % field_label.capitalize()
    
class ProductForm(BaseForm):

    class Meta:
        model = Product
        fields = ['sku','name','category','description','detail','is_active']
        widgets = {
            "detail": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5"}, config_name="extends"
            )
        }
                            
class ProductAttributeForm(BaseForm):
    class Meta:
        model = ProductAttribute
        fields = ['name']

class VariantForm(BaseForm):
    
    class Meta:
        model = Variant
        fields = ['price', 'stock']
        localized_fields = ['price', 'stock']
    
class GalleryForm(BaseForm):
    image = forms.ImageField(widget=forms.FileInput)
    
    class Meta:
        model = Gallery
        fields = ['image']

class CategoryForm(BaseForm):
    
    class Meta:
        model = Category
        fields = ['name','is_active']

class OrderForm(BaseForm):
    
    class Meta:
        model = Order
        fields = ['invoice','user','shipping_address','payment','total_price','shipping_cost','status']

class OrderItemForm(BaseForm):
    class Meta:
        model = OrderItem
        fields = ['product']

OrderFormSet = inlineformset_factory(User,Order,form=OrderForm,extra=0,can_delete=True)
OrderItemFormSet = inlineformset_factory(Order,OrderItem,form=OrderItemForm,extra=0,can_delete=True)
GalleryFormSet = inlineformset_factory(Product,Gallery,form=GalleryForm,extra=0,can_delete=True)
CategoryFormSet = inlineformset_factory(Category,Category,form=CategoryForm,extra=0,can_delete=True)
