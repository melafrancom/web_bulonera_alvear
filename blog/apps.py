"""Blog App Configuration"""
from django.apps import AppConfig


class BlogConfig(AppConfig):
    """Configuration for the Blog app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'
    verbose_name = 'Blog'

    def ready(self):
        """Import signals when app is ready"""
        import blog.signals  # noqa
