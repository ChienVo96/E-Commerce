from import_export import resources
from import_export.fields import Field
from import_export.widgets import IntegerWidget
from core.models import Category

class CategoryResource(resources.ModelResource):
    name = Field(attribute='name', column_name="Tên Danh Mục")
    is_active = Field(attribute='is_active', column_name="Kích Hoạt",widget=IntegerWidget())
    class Meta:
        model = Category
        fields = ['name','is_active']
        import_id_fields = ['name']  # Đảm bảo 'name' là trường duy nhất dùng để đối chiếu
        skip_unchanged = True 