from rest_framework import serializers
from apps.activesTree.api.models.index import Carpeta

class RecursiveFolderSerializer(serializers.ModelSerializer):
    subfolders = serializers.SerializerMethodField()
    compania_info = serializers.SerializerMethodField()
    machine_info = serializers.SerializerMethodField()
    muestra_info = serializers.SerializerMethodField()
    sampling_points = serializers.SerializerMethodField()
    
    class Meta:
        model = Carpeta
        fields = [
            'id', 'nombre', 'typeFolder', 'id_parent_node', 
            'compania_info', 'machine_info', 'muestra_info', 'sampling_points', 'subfolders'
        ]
    
    def get_subfolders(self, obj):
        children_by_parent = self.context.get('children_by_parent', {})
        subfolders = children_by_parent.get(str(obj.id), [])
        return RecursiveFolderSerializer(
            subfolders,
            many=True,
            context=self.context,
        ).data
    
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

    def get_sampling_points(self, obj):
        if not obj.machine_id:
            return []
        return [
            {
                'id': point.id,
                'nombre': point.nombre,
                'codigo': point.codigo,
                'descripcion': point.descripcion,
                'activo': point.activo,
                'muestras_asociadas': getattr(point, 'muestras_asociadas', 0),
            }
            for point in obj.machine.puntos_muestreo.all() if point.activo
        ]
