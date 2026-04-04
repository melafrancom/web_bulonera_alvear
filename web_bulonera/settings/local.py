from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

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
