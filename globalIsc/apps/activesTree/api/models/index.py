from django.db import models
from apps.misc.api.models.companies.index import Empresa
from apps.muestras.api.models.muestras.index import Muestra
from apps.activesTree.api.models.machines.index import Maquina

class Carpeta(models.Model):
    
    is_pt_medida=models.BooleanField(default=False)
    id_parent_node=models.CharField(max_length=255,default='-1')
    nombre = models.CharField(max_length=255)
    parentId=models.CharField(max_length=255,default="root")
    compania = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="compañia")
    typeFolder=models.CharField(max_length=255)
    isMachine=models.BooleanField(default=False)
    machine = models.ForeignKey(
        Maquina, 
        on_delete=models.CASCADE, 
        related_name="maquina_folder",
        null=True,        # ← Permitir nulo en BD
        blank=True        # ← Permitir en blanco en formularios
        # ← QUITAR el default
    )
    muestra = models.ForeignKey(
        Muestra, 
        on_delete=models.CASCADE, 
        related_name="muestra_folder",
        null=True,        # ← Permitir nulo en BD
        blank=True        # ← Permitir en blanco en formularios
        # ← QUITAR el default
    )
    
    def __str__(self):
        return f"{self.nombre} ({self.compañia.nombre})"





