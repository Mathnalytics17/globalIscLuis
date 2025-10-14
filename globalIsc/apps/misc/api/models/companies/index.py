from django.db import models

class Empresa(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)  # Hacer email opcional
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    is_active=models.BooleanField(default=True)

    descripcion= models.TextField(blank=True)

    def __str__(self):
        return self.nombre