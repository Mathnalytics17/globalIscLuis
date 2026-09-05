from rest_framework import serializers
from rest_framework import serializers

from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.pruebas.index import Prueba


class EmpresaTipoGestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = ["id", "nombre"]


class TipoGestionMuestraSerializer(serializers.ModelSerializer):
    empresas_permitidas_info = EmpresaTipoGestionSerializer(
        source="empresas_permitidas",
        many=True,
        read_only=True
    )
    pruebas_sugeridas = serializers.PrimaryKeyRelatedField(
        queryset=Prueba.objects.filter(activo=True),
        many=True,
        required=False,
    )
    pruebas_sugeridas_info = serializers.SerializerMethodField()

    class Meta:
        model = TipoGestionMuestra
        fields = [
            "id",
            "nombre",
            "dias_habiles",
            "dias_calendario",
            "aplica_a_todos",
            "empresas_permitidas",
            "empresas_permitidas_info",
            "pruebas_sugeridas",
            "pruebas_sugeridas_info",
            "activo",
            "deleted_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "empresas_permitidas": {"required": False},
            "deleted_at": {"read_only": True},
        }

    def get_pruebas_sugeridas_info(self, obj):
        return [
            {
                "id": prueba.id,
                "nombre_variable": prueba.nombre_variable,
                "acronimo": prueba.acronimo,
                "unidad_medida": prueba.unidad_medida,
            }
            for prueba in obj.pruebas_sugeridas.filter(activo=True).order_by("nombre_variable")
        ]
