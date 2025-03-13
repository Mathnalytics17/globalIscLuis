from django.db import models
from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.api.models.analysis.index import AnalisisLubricante


class Carpeta(models.Model):
   
    is_pt_medida=models.BooleanField(default=False)
    id_parent_node=models.CharField(max_length=255,default='-1')
    nombre = models.CharField(max_length=255)
    parentId=models.CharField(max_length=255,default="root")
    compania = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="carpetas")
    typeFolder=models.CharField(max_length=255)
    isMachine=models.BooleanField(default=False)
    def __str__(self):
        return f"{self.nombre} ({self.compañia.nombre})"





