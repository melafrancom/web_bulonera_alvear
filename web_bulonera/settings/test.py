from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Seguridad desactivada para tests
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Email silenciado
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Meta Pixel desactivado
META_PIXEL_ENABLED = False

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Contact Email Variables
CONTACT_EMAIL = 'test_owner@bulonera.com'
EMAIL_TO_SEND_MESSAGES = 'test_owner@bulonera.com'
DEFAULT_FROM_EMAIL = 'noreply@bulonera.com'
