from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.misc.api.models.roles.index import Rol
from apps.misc.api.models.companies.index import Empresa

class Usuario(AbstractUser):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="usuarios")
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.username} - {self.empresa.nombre} ({self.rol.nombre if self.rol else 'Sin Rol'})"
