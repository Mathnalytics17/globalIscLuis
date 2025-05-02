import os
from pathlib import Path
from dotenv import load_dotenv

from datetime import timedelta  # Añade esta importación al inicio de tu archivo
# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import os
from dotenv import load_dotenv

load_dotenv()
get_env = os.getenv



 # Starting the gspread client when our server starts speeds things up; it avoids re-authenticating on each request
load_dotenv()
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-u8*sd_ika1*x+ww@$j5)u8-(m6%&k)=7l4kr=5ayd1@(l36mf_'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'apps.activesTree',
    'apps.users',
    'apps.misc','apps.muestras','apps.reporte','apps.resultado','django_filters',
]


CORS_ALLOW_CREDENTIALS = True  # Permite el envío de credenciales (cookies, auth headers)

SESSION_COOKIE_SAMESITE = 'None'  # Necesario para cross-site cookies
SESSION_COOKIE_SECURE = True  # Solo enviar cookies sobre HTTPS (en producción)
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
FRONTEND_URL='http://localhost:3000'
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

ROOT_URLCONF = 'backend.urls'
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React/Vue/Angular en desarrollo
    "http://82.112.250.23",  # Dominio en producción
    "http://82.112.250.23:1337",
    "https://www.altasfundacionaladina.org",
    "https://altasfundacionaladina.org",
    "http://82.112.250.23:3000",
      "http://127.0.0.1:3000",
    
]


CORS_TRUSTED_ORIGINS = [
    "http://localhost:3000",  # React/Vue/Angular en desarrollo
    "http://82.112.250.23",  # Dominio en producción
    "http://82.112.250.23:1337",
    "https://www.altasfundacionaladina.org",
    "https://altasfundacionaladina.org",
    "http://82.112.250.23:3000",
]


CORS_ORIGINS_WHITELIST = [
    "http://localhost:3000",  # React/Vue/Angular en desarrollo
    "http://82.112.250.23",  # Dominio en producción
    "http://82.112.250.23:1337",
    "https://altasfundacionaladina.org",
    "http://82.112.250.23:3000",
]

MIDDLEWARE = [
   'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]



REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}
SIMPLE_JWT = {
    'ROTATE_REFRESH_TOKENS': True,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10000),  # Más seguro
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
   'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'globaliscdb',  # Reemplaza con el nombre de tu base de datos
        'USER': 'postgres',     # Reemplaza con tu nombre de usuario de PostgreSQL
        'PASSWORD':'1',  # Reemplaza con tu contraseña de PostgreSQL
        'HOST': 'localhost',  # Reemplaza con la dirección de tu servidor PostgreSQL (puede ser 'localhost' o una IP)
        'PORT': '5432',        # Reemplaza con el puerto de tu servidor PostgreSQL (el puerto por defecto es 5432)
    }
}



# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Backend por defecto
    'backend.auth.EmailAuthBackend.EmailAuthBackend',  # Tu backend personalizado
]
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Custom User Model
AUTH_USER_MODEL = 'users.User'

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Configuración de tokens
EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS = 3  # Días de validez para verificación de email
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 24  # Horas de validez para reseteo de contraseña


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'djangopruebas61@gmail.com'  # Tu email completo
EMAIL_HOST_PASSWORD = 'zisz tacf eakn kckl'  # Contraseña de aplicación
DEFAULT_FROM_EMAIL = 'djangopruebas61@gmail.com'

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/
