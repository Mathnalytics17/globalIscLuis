from rest_framework import serializers
from apps.misc.api.serializers.lubricante.index import LubricanteSerializer
from apps.misc.api.serializers.tipoEquipo.index import ReferenciaEquipoSerializer
from apps.users.api.serializers.index import UserSerializer
from apps.muestras.api.models.muestras.index import Muestra
from apps.activesTree.api.serializers.index import MaquinaSerializer


class MuestraSerializer(serializers.ModelSerializer):
    #cliente = ClienteSerializer()
    lubricante = LubricanteSerializer()
    referencia_equipo = ReferenciaEquipoSerializer()
    usuario_registro = UserSerializer()
    Equipo=MaquinaSerializer()
    class Meta:
        model = Muestra
        fields = '__all__'

        
class CreateMuestraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Muestra
        fields = '__all__'
        read_only_fields = ['id', 'usuario_registro', 'fecha_registro']