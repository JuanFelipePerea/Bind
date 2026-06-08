from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-fallback-key-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]

# Render.com inyecta RENDER_EXTERNAL_HOSTNAME automáticamente en producción
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = (
    [f'https://{_render_host}'] if _render_host else []
) + [
    o.strip()
    for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'cloudinary',
    'django.contrib.staticfiles',
    'anymail',
    'django.contrib.sites',

    # django-allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    'accounts',
    'events',
    'modules',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'BindV1.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'events.context_processors.bynix_credits',
            ],
        },
    },
]

WSGI_APPLICATION = 'BindV1.wsgi.application'


_db_url = os.environ.get('DATABASE_URL') or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {'default': dj_database_url.parse(_db_url, conn_max_age=600)}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Django 6.0 admin CSS references icon-debug.svg which doesn't resolve during
# collectstatic. This tells WhiteNoise to warn instead of crashing.
WHITENOISE_MANIFEST_STRICT = False

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY':    os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
}

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "BindV1.storage.ManifestStorage",
    },
}

# django-cloudinary-storage accede a settings.STATICFILES_STORAGE, que Django 6.0
# eliminó de global_settings.py. Este shim evita el AttributeError en el startup.
STATICFILES_STORAGE = "BindV1.storage.ManifestStorage"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# Cache
# En Render (producción) usa DatabaseCache para que los créditos de Bynix y
# otros valores cacheados sobrevivan reinicios y sean compartidos entre
# workers de Gunicorn.  En desarrollo local se mantiene LocMemCache (defecto
# de Django) para no requerir infraestructura adicional.
# IMPORTANTE: al desplegar por primera vez en Render ejecuta una sola vez:
#   python manage.py createcachetable
# ---------------------------------------------------------------------------
if os.environ.get('RENDER'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'bind_cache_table',
        }
    }

LOGIN_REDIRECT_URL = '/dashboard/'
LOGIN_URL = '/accounts/login/'

# Email (para 2FA e invitaciones)
# En desarrollo: EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend en .env
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'BIND <noreply@bind.onrender.com>')

_brevo_key = os.environ.get('BREVO_API_KEY', '')
if _brevo_key:
    EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
    ANYMAIL = {'BREVO_API_KEY': _brevo_key}
else:
    EMAIL_BACKEND = os.environ.get(
        'EMAIL_BACKEND',
        'django.core.mail.backends.console.EmailBackend',
    )
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '465'))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False') == 'True'
    EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True') == 'True'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')


# ---------------------------------------------------------------------------
# django-allauth
# ---------------------------------------------------------------------------
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = os.environ.get(
    'ACCOUNT_HTTP_PROTOCOL', 'http' if DEBUG else 'https'
)

# ── Social auth ──────────────────────────────────────────────────────────────
# AUTO_SIGNUP=True salta el formulario /3rdparty/signup/ cuando el provider
# entrega todos los datos necesarios (email, en nuestro caso).
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'

# Si el email de Google coincide con un User existente → iniciar sesión
# directamente y conectar el SocialAccount (no pedir registro).
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_ADAPTER = 'accounts.adapters.BindSocialAccountAdapter'

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

# URL canónica del sitio — usada para generar links en emails enviados desde el backend.
# En producción debe coincidir con el dominio público (ej. https://bind-gexm.onrender.com).
# Si no se define, los links se construyen a partir del request (funciona bien en local).
SITE_URL = os.environ.get('SITE_URL', '').rstrip('/')

# Persiste access_token + refresh_token en la tabla socialaccount_socialtoken
SOCIALACCOUNT_STORE_TOKENS = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
    }
}

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
