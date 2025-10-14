from rest_framework import serializers
from apps.muestras.api.models.muestras.index import Muestra
from apps.misc.api.serializers.lubricante.index import LubricanteSerializer
from apps.muestras.api.serializers.pruebasMuestra.index import PruebaMuestraSerializer

class CreateMuestraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Muestra
        fields = '__all__'
        extra_kwargs = {
            'usuario_registro': {'required': False},
            'id': {'read_only': True}
        }

    def create(self, validated_data):
        if 'usuario_registro' not in validated_data and self.context.get('request'):
            validated_data['usuario_registro'] = self.context['request'].user
        return super().create(validated_data)

class MuestraListSerializer(serializers.ModelSerializer):
    referencia_equipo_info = serializers.SerializerMethodField()
    lubricante = LubricanteSerializer()
    resultados = PruebaMuestraSerializer(many=True, read_only=True)
    pruebas_estructuradas = serializers.SerializerMethodField()
    
    class Meta:
        model = Muestra
        fields = '__all__'
    
    def get_referencia_equipo_info(self, obj):
        if obj.referencia_equipo:
            empresa_data = None
            if obj.referencia_equipo.empresa:
                empresa_data = {
                    'id': obj.referencia_equipo.empresa.id,
                    'nombre': obj.referencia_equipo.empresa.nombre,
                    # Agrega otros campos que necesites de la empresa
                }
            
            return {
                'id': obj.referencia_equipo.id,
                'nombre': obj.referencia_equipo.nombre,
                'codigo_equipo': obj.referencia_equipo.codigo_equipo,
                'empresa': empresa_data  # ✅ Ahora serializado correctamente
            }
        return None
 
    def get_pruebas_estructuradas(self, obj):
        """Organiza las pruebas en estructura jerárquica usando is_subPrueba y parent_node"""
        try:
            todas_pruebas = obj.resultados.all()
            
            # Separar pruebas padres (is_subPrueba=False) e hijas (is_subPrueba=True)
            pruebas_padres = [p for p in todas_pruebas if not p.prueba.is_subPrueba]
            pruebas_hijas = [p for p in todas_pruebas if p.prueba.is_subPrueba]
            
            # Crear estructura jerárquica
            pruebas_estructuradas = []
            
            for prueba_padre in pruebas_padres:
                # Serializar el padre
                padre_data = PruebaMuestraSerializer(prueba_padre).data
                padre_data['subpruebas'] = []
                
                # Buscar subpruebas que tengan parent_node = id del padre
                for prueba_hija in pruebas_hijas:
                    if prueba_hija.prueba.parent_node == prueba_padre.prueba.id:
                        hija_data = PruebaMuestraSerializer(prueba_hija).data
                        padre_data['subpruebas'].append(hija_data)
                
                pruebas_estructuradas.append(padre_data)
            
            return pruebas_estructuradas
        except Exception as e:
            
            return []
        
class MuestraSerializer(serializers.ModelSerializer):
    referencia_equipo_info = serializers.SerializerMethodField()
    lubricante = LubricanteSerializer()
    # ✅ CORREGIDO: agregar many=True para la relación uno-a-muchos
    resultados = PruebaMuestraSerializer(many=True, read_only=True)
    # Estructura jerárquica basada en is_subPrueba y parent_node
    pruebas_estructuradas = serializers.SerializerMethodField()
    
    class Meta:
        model = Muestra
        fields = '__all__'
    
    def get_pruebas_estructuradas(self, obj):
        """Organiza las pruebas en estructura jerárquica usando is_subPrueba y parent_node"""
        todas_pruebas = obj.resultados.all()
        
        # Separar pruebas padres (is_subPrueba=False) e hijas (is_subPrueba=True)
        pruebas_padres = [p for p in todas_pruebas if not p.prueba.is_subPrueba]
        pruebas_hijas = [p for p in todas_pruebas if p.prueba.is_subPrueba]
        
        # Crear estructura jerárquica
        pruebas_estructuradas = []
        
        for prueba_padre in pruebas_padres:
            # Serializar el padre
            padre_data = PruebaMuestraSerializer(prueba_padre).data
            padre_data['subpruebas'] = []
            
            # Buscar subpruebas que tengan parent_node = id del padre
            for prueba_hija in pruebas_hijas:
                if prueba_hija.prueba.parent_node == prueba_padre.prueba.id:
                    hija_data = PruebaMuestraSerializer(prueba_hija).data
                    padre_data['subpruebas'].append(hija_data)
            
            pruebas_estructuradas.append(padre_data)
        
        return pruebas_estructuradas
    
    def get_referencia_equipo_info(self, obj):
        if obj.referencia_equipo:
            # Obtener información de la empresa asociada a la máquina
            empresa_info = None
            if obj.referencia_equipo.empresa:
                # Obtener usuarios asociados a la empresa
                usuarios = obj.referencia_equipo.empresa.user_set.all()
                usuarios_data = [
                    {
                        'id': usuario.id,
                        'email': usuario.email,
                        'first_name': usuario.first_name,
                        'last_name': usuario.last_name,
                        'role': usuario.role,
                        'is_active': usuario.is_active,
                        'email_verified': usuario.email_verified,
                        'phone': usuario.phone
                    }
                    for usuario in usuarios
                ]
                
                empresa_info = {
                    'id': obj.referencia_equipo.empresa.id,
                    'nombre': obj.referencia_equipo.empresa.nombre,
                    'direccion': obj.referencia_equipo.empresa.direccion,
                    'telefono': obj.referencia_equipo.empresa.telefono,
                    'email': obj.referencia_equipo.empresa.email,
                    'is_active': obj.referencia_equipo.empresa.is_active,
                    'usuarios': usuarios_data,
                    'total_usuarios': len(usuarios_data)
                }
            
            return {
                'id': obj.referencia_equipo.id,
                'nombre': obj.referencia_equipo.nombre,
                'codigo_equipo': obj.referencia_equipo.codigo_equipo,
                'numero_serie': obj.referencia_equipo.numero_serie,
                'componente': obj.referencia_equipo.componente,
                'tipoAceite': obj.referencia_equipo.tipoAceite,
                'frecuenciaCambio': obj.referencia_equipo.frecuenciaCambio,
                'frecuenciaAnalisis': obj.referencia_equipo.frecuenciaAnalisis,
                'empresa_info': empresa_info  # ✅ Ahora incluye los usuarios
            }
        return None