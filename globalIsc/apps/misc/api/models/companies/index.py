from django.db import models

class Empresa(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activa"
        READ_ONLY = "READ_ONLY", "Solo lectura"
        BLOCKED = "BLOCKED", "Bloqueada"
        INACTIVE = "INACTIVE", "Inactiva"

    nombre = models.CharField(max_length=255, unique=True)
    nit = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)  # Hacer email opcional
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    is_active=models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    read_only_until = models.DateTimeField(blank=True, null=True)
    retention_until = models.DateTimeField(blank=True, null=True)
    blocked_at = models.DateTimeField(blank=True, null=True)
    block_reason = models.TextField(blank=True)

    descripcion= models.TextField(blank=True)

    def __str__(self):
        return self.nombre
