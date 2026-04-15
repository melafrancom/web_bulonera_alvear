from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),  # Debes crear esta base de datos primero
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),  # La contraseña que estableciste para root
        'HOST': env('DB_HOST', default='localhost'),  # o 127.0.0.1
        'PORT': env('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_spanish_ci',
            'init_command': "SET NAMES 'utf8mb4' COLLATE 'utf8mb4_spanish_ci';"
        }
    }
}

# Seguridad relajada para desarrollo
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# Meta Pixel desactivado en desarrollo
META_PIXEL_ENABLED = False

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('SMTP_HOST')
EMAIL_PORT = env('SMTP_PORT')
EMAIL_HOST_USER = env('SMTP_USER')
EMAIL_HOST_PASSWORD = env('SMTP_PASSWORD')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env('EMAIL_TO_SEND_MESSAGES', default='contacto@buloneraalvear.online')
CONTACT_EMAIL = env('EMAIL_TO_RECEIVE_MESSAGES', default='contacto@buloneraalvear.online')
