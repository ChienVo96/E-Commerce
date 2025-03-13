from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import set_language
from django.views.i18n import JavaScriptCatalog
from account.views import LoginView,LogoutView


urlpatterns = [
    path('', include('store.urls')),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('account/', include('account.urls')),
    path('login/', LoginView.as_view(),name='login'),
    path('logout/', LogoutView.as_view(),name='logout'),
    path('core/', include('core.urls')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('set-language/', set_language, name='set_language'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
