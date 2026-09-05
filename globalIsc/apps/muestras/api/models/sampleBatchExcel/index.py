import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class SampleBatchExcelTemplateToken(models.Model):
    """
    Token de control para plantillas Excel de ingreso masivo de muestras.

    No intenta convertir Excel en una fuente confiable. Excel solo es una interfaz
    de captura. El backend siempre valida token, estructura, catálogos y filas.
    """

    SCHEMA_VERSION = "sample-batch-v1"

    id = models.BigAutoField(primary_key=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    schema_version = models.CharField(max_length=50, default=SCHEMA_VERSION)
    filename = models.CharField(max_length=180, blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="sample_batch_excel_templates",
    )
    cliente_empresa_id = models.CharField(max_length=80, blank=True, null=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["schema_version"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.schema_version} - {self.token}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_expired
