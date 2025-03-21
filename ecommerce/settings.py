"""
Django settings for dcrm project.

Generated by 'django-admin startproject' using Django 4.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from datetime import timedelta
import os
from dotenv import load_dotenv
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from import_export.formats.base_formats import XLS, XLSX

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Tải các biến môi trường từ tệp .env
load_dotenv()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-pn(=lk@8=_-!251!3(1*l)0bhp_dd^3ytmqv^_0=*b+3)t7@tz'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    "corsheaders",
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_ckeditor_5',
    'import_export',
    'api',
    'account',
    'core',
    "store",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
]

ROOT_URLCONF = 'ecommerce.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecommerce.wsgi.application'
ASGI_APPLICATION = 'ecommerce.asgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_NAME'),
        'USER': os.environ.get('POSTGRES_USER'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
        'HOST': os.environ.get('HOST'),
        'PORT': os.environ.get('PORT'),
    }
}




# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS':{
            'min_length':3,
        }
    },
    # {
    #     'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    # },
    # {
    #     'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    # },
]

AUTHENTICATION_BACKENDS = [
    'account.backends.EmailOrPhoneBackend',
    'django.contrib.auth.backends.ModelBackend',  # Keep the default backend
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'vi-VN'

TIME_ZONE = 'Asia/Saigon'

USE_I18N = True

USE_TZ = True

USE_L10N = False

LANGUAGES = (
    ('en-US', 'English'),
    ('vi-VN', 'Tiếng Việt'),
)

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'

# Cấu hình STATIC_ROOT
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Đảm bảo thư mục này tồn tại trong container hoặc máy chủ của bạn

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_DOMAIN = os.getenv('SITE_DOMAIN', 'http://127.0.0.1:8000')
MAX_AVATAR_SIZE = 1 * 1024 * 1024  # 1MB
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'store:index'
LOGOUT_REDIRECT_URL = 'store:index'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # Sử dụng console backend thay vì gửi email thực tế
DEFAULT_FROM_EMAIL = 'e-commerce@mail.com'  # Địa chỉ email gửi đi mặc định

AUTH_USER_MODEL = "core.User"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"

NUMBER_GROUPING = 3
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
DATE_FORMAT = 'd/m/Y'

customColorPalette = [
    {
        'color': 'hsl(4, 90%, 58%)',
        'label': 'Red'
    },
    {
        'color': 'hsl(340, 82%, 52%)',
        'label': 'Pink'
    },
    {
        'color': 'hsl(291, 64%, 42%)',
        'label': 'Purple'
    },
    {
        'color': 'hsl(262, 52%, 47%)',
        'label': 'Deep Purple'
    },
    {
        'color': 'hsl(231, 48%, 48%)',
        'label': 'Indigo'
    },
    {
        'color': 'hsl(207, 90%, 54%)',
        'label': 'Blue'
    },
]
CKEDITOR_5_FILE_STORAGE = "core.storage.CustomStorage"
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': ['heading', '|', 'bold', 'italic', 'link',
                    'bulletedList', 'numberedList', 'blockQuote', 'imageUpload', ],
    },
    'extends': {
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3',
            '|',
            'bulletedList', 'numberedList',
            '|',
            'blockQuote',
        ],
        'toolbar': ['heading', '|', 'outdent', 'indent', '|', 'bold', 'italic', 'link', 'underline', 'strikethrough','insertTable','insertImage',
        'highlight', '|',  'bulletedList', 'numberedList', 'todoList', '|',  'blockQuote', '|','fontSize', 'fontFamily', 'fontColor', 
        'fontBackgroundColor', 'mediaEmbed', 'removeFormat',
        ],
        'image': {
            'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft',
                        'imageStyle:alignRight', 'imageStyle:alignCenter', 'imageStyle:side',  '|'],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignRight',
                'alignCenter',
            ]

        },
        'table': {
            'contentToolbar': [ 'tableColumn', 'tableRow', 'mergeTableCells',
            'tableProperties', 'tableCellProperties' ],
            'tableProperties': {
                'borderColors': customColorPalette,
                'backgroundColors': customColorPalette
            },
            'tableCellProperties': {
                'borderColors': customColorPalette,
                'backgroundColors': customColorPalette
            }
        },
        'heading' : {
            'options': [
                { 'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph' },
                { 'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1' },
                { 'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2' },
                { 'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3' }
            ]
        },
        'height': 500,
        'width': '100%',
        'language': 'vi',
    },
    'list': {
        'properties': {
            'styles': 'true',
            'startIndex': 'true',
            'reversed': 'true',
        }
    }
}

CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"

LANGUAGE_COOKIE_NAME = 'language'  # Tên cookie mặc định
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 30  # Thời gian sống của cookie (30 ngày)
LANGUAGE_COOKIE_PATH = '/'  # Đường dẫn áp dụng cookie
LANGUAGE_COOKIE_SECURE = False  # Nếu bạn sử dụng HTTPS

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis/1',  # Kết nối với Redis server trên localhost, database 1
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",  # Redis Channel Layer
        "CONFIG": {
            "hosts": [('redis', 6379)],  # 'redis' là tên dịch vụ Redis trong Docker Compose
        },
    },
}

REST_FRAMEWORK = {
    # Cấu hình xác thực (Authentication)
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],

    # Cấu hình quyền truy cập (Permission)
    'DEFAULT_PERMISSION_CLASSES': [
        # Quyền truy cập mặc định: yêu cầu người dùng phải xác thực để thực hiện POST, PUT, DELETE. 
        # Các yêu cầu GET có thể được thực hiện mà không cần xác thực.
        'rest_framework.permissions.IsAuthenticatedOrReadOnly', 
    ],

    # Cấu hình renderer (định dạng phản hồi)
    'DEFAULT_RENDERER_CLASSES': [
        # Định dạng phản hồi mặc định là JSON. Tất cả các response sẽ được trả về dưới dạng JSON.
        'rest_framework.renderers.JSONRenderer',  
    ],

    # Cấu hình filter (lọc dữ liệu)
    'DEFAULT_FILTER_BACKENDS': [
        # Sử dụng DjangoFilterBackend cho việc lọc dữ liệu theo các trường từ các truy vấn URL (query parameters).
        'django_filters.rest_framework.DjangoFilterBackend', 
    ],

    # Cấu hình phân trang (Pagination)
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',  
    'PAGE_SIZE': 10,  # Mỗi trang sẽ có tối đa 10 đối tượng.

    # Cấu hình throttle (giới hạn tốc độ yêu cầu)
    'DEFAULT_THROTTLE_CLASSES': [
        # Áp dụng ScopedRateThrottle, cho phép giới hạn số lượng yêu cầu từ client trong một phạm vi (scope) cụ thể.
        'rest_framework.throttling.ScopedRateThrottle',  
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Giới hạn 1000 yêu cầu mỗi ngày cho tất cả các view mặc định không có throttle_scope riêng.
        'default': '1000/day',  
    },

    # Cấu hình exception handler (xử lý lỗi)
    'EXCEPTION_HANDLER': 'api.exception.custom_exception_handler'
}


CORS_ALLOW_ALL_ORIGINS = True
# CORS_ALLOWED_ORIGINS = [
#     "http://127.0.0.1:8000",
#     "http://localhost:8000",
# ]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',  # Thêm domain của frontend vào đây
    'http://localhost:8000',
]


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
}

CSRF_COOKIE_NAME = 'csrftoken'  # Tên cookie chứa CSRF token
CSRF_COOKIE_HTTPONLY = True  # Ngăn không cho JavaScript truy cập vào cookie CSRF
CSRF_COOKIE_SECURE = True  # Đảm bảo chỉ gửi cookie qua kết nối HTTPS
CSRF_COOKIE_SAMESITE = 'Lax'   # Cấu hình SameSite cookie (Lax giúp giảm khả năng bị CSRF trong các tình huống thông thường)

SESSION_COOKIE_AGE = timedelta(days=1).total_seconds()
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'   # Cấu hình SameSite cookie (Lax giúp giảm khả năng bị CSRF trong các tình huống thông thường)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'  # Tên của cache alias

IMPORT_EXPORT_FORMATS = [XLSX]