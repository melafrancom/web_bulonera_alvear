from django.apps import AppConfig


class MediaBankConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'media_bank'
    verbose_name = 'Banco de Imágenes'

    def ready(self):
        import media_bank.signals  # noqa: F401
