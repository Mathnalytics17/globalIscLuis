from rest_framework import serializers
from apps.activesTree.api.models.index import Carpeta

from apps.activesTree.api.models.index import Maquina
from apps.muestras.api.models.muestras.index import Muestra

class RecursiveFolderSerializer(serializers.ModelSerializer):
    subfolders = serializers.SerializerMethodField()
    compania_info = serializers.SerializerMethodField()
    machine_info = serializers.SerializerMethodField()
    muestra_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Carpeta
        fields = [
            'id', 'nombre', 'typeFolder', 'id_parent_node', 
            'compania_info', 'machine_info', 'muestra_info', 'subfolders'
        ]
    
    def get_subfolders(self, obj):
        # Precargar relaciones para optimizar
        subfolders = Carpeta.objects.filter(id_parent_node=str(obj.id)).select_related(
            'compania', 'machine', 'muestra'
        )
        return RecursiveFolderSerializer(subfolders, many=True).data
    
    def get_compania_info(self, obj):
        if obj.compania:
            return {
                'id': obj.compania.id,
                'nombre': obj.compania.nombre,
                'direccion': obj.compania.direccion,
                'telefono': obj.compania.telefono,
                'email': obj.compania.email
            }
        return None
    
    def get_machine_info(self, obj):
        if obj.machine:
            return {
                'id': obj.machine.id,
                'nombre': obj.machine.nombre,
                'codigo_equipo': obj.machine.codigo_equipo,
                'numero_serie': obj.machine.numero_serie,
                'componente': obj.machine.componente,
                'tipoAceite': obj.machine.tipoAceite
            }
        return None
    
    def get_muestra_info(self, obj):
        if obj.muestra:
            return {
                'id': obj.muestra.id,
                'fecha_toma': obj.muestra.fecha_toma,
                'contacto_cliente': obj.muestra.contacto_cliente,
                'observaciones': obj.muestra.observaciones,
                'is_ingresado': obj.muestra.is_ingresado,
                'is_revisado': obj.muestra.is_revisado,
                'is_resultado_ingresado': obj.muestra.is_resultado_ingresado
            }
        return None