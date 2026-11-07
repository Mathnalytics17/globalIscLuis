from django.apps import AppConfig


class ReporteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reporte'

    def ready(self):
        from apps.reporte import signals  # noqa: F401
