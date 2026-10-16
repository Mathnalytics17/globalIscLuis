from django.apps import AppConfig


class ActivestreeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.activesTree'

    def ready(self):
        from . import signals  # noqa: F401
