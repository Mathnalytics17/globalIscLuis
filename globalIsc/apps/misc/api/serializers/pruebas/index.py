from rest_framework import serializers
from apps.misc.api.models.pruebas.index import Prueba
from django.contrib.contenttypes.models import ContentType

class PruebaSerializer(serializers.ModelSerializer):
    pruebas_estructuradas = serializers.SerializerMethodField()
    prueba_padre = serializers.SerializerMethodField()
    limites = serializers.SerializerMethodField()  # Nuevo campo para límites
    
    class Meta:
        model = Prueba
        fields = '__all__'
    
    def get_pruebas_estructuradas(self, obj):
        """Organiza solo las subpruebas directas de esta prueba"""
        if obj.is_subPrueba:
            return []  # Si ya es subprueba, no tiene hijos
        
        # Buscar subpruebas que tengan parent_node = id de esta prueba
        subpruebas = Prueba.objects.filter(
            parent_node=obj.id, 
            activo=True,
            is_subPrueba=True
        )
        
        subpruebas_data = []
        for subprueba in subpruebas:
            subprueba_data = {
                'id': subprueba.id,
                'codigo': subprueba.codigo,
                'nombre': subprueba.nombre,
                'descripcion': subprueba.descripcion,
                'metodo_referencia': subprueba.metodo_referencia,
                'unidad_medida': subprueba.unidad_medida,
                'is_subPrueba': subprueba.is_subPrueba,
                'parent_node': subprueba.parent_node,
                'categoria': subprueba.categoria,
                'activo': subprueba.activo,
                'limites': self.get_limites_for_prueba(subprueba)  # Límites para subpruebas también
            }
            subpruebas_data.append(subprueba_data)
        
        return subpruebas_data

    def get_prueba_padre(self, obj):
        """Obtiene la información de la prueba padre si es una subprueba"""
        if not obj.is_subPrueba or obj.parent_node == -1:
            return None
        
        try:
            # Buscar la prueba padre
            prueba_padre = Prueba.objects.get(id=obj.parent_node, activo=True)
            return {
                'id': prueba_padre.id,
                'codigo': prueba_padre.codigo,
                'nombre': prueba_padre.nombre,
                'descripcion': prueba_padre.descripcion,
                'metodo_referencia': prueba_padre.metodo_referencia,
                'unidad_medida': prueba_padre.unidad_medida,
                'categoria': prueba_padre.categoria,
                'limites': self.get_limites_for_prueba(prueba_padre)  # Límites para padre
            }
        except Prueba.DoesNotExist:
            return None

    def get_limites(self, obj):
        """Obtiene los límites asociados a la prueba a través del polimorfismo"""
        return self.get_limites_for_prueba(obj)

    def get_limites_for_prueba(self, prueba_obj):
        """Función auxiliar para obtener límites de cualquier objeto Prueba"""
        try:
            # Buscar la relación PruebaLimite para esta prueba
            prueba_limite = prueba_obj.limite_asignado
            
            if not prueba_limite:
                return None
            
            # Obtener el objeto límite a través del GenericForeignKey
            limite_obj = prueba_limite.limite
            
            if not limite_obj:
                return None
            
            # Serializar según el tipo de límite
            content_type = ContentType.objects.get_for_model(limite_obj)
            
            if content_type.model == 'limitegenericoprueba':
                return {
                    'tipo': 'generico',
                    'nombre': limite_obj.nombre,
                    'valor': limite_obj.valor,
                    'symbol_operation': limite_obj.symbol_operation,
                    'type_operation': limite_obj.type_operation
                }
            
            elif content_type.model == 'limitecalidad':
                return {
                    'tipo': 'calidad',
                    'c1': limite_obj.c1,
                    'c2': limite_obj.c2,
                    'seq_espuma': limite_obj.seq_espuma,
                    'chispa': limite_obj.chispa,
                    'valor': limite_obj.valor
                }
            
            elif content_type.model == 'limiteviscosidad':
                return {
                    'tipo': 'viscosidad',
                    'v1': limite_obj.v1,
                    'v2': limite_obj.v2,
                    'vmin': limite_obj.vmin,
                    'vmax': limite_obj.vmax,
                    'iv1': limite_obj.iv1,
                    'iv2': limite_obj.iv2
                }
            
            elif content_type.model == 'elementoanalisis':
                # Para ElementoAnalisis, también traer los comentarios asociados
             
                
                return {
                    'tipo': 'elemento_analisis',
                    'simbolo': limite_obj.simbolo,
                    'nombre': limite_obj.nombre,
                    'valor': limite_obj.valor,
                    'symbol_operation': limite_obj.symbol_operation,

                }
            
            else:
                return {
                    'tipo': 'desconocido',
                    'content_type': content_type.model,
                    'object_id': prueba_limite.object_id
                }
                
        except Exception as e:
            # Si no hay límites asociados o hay algún error, retornar None
            return None