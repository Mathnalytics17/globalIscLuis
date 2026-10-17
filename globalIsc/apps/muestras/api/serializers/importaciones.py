from rest_framework import serializers
from apps.muestras.api.models.importaciones import CorridaImportacion


class CorridaImportacionSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    actor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CorridaImportacion
        fields = "__all__"
        read_only_fields = ("actor", "creado_en", "finalizado_en", "revertida_en")

    def get_actor_nombre(self, obj):
        return obj.actor.get_full_name() or obj.actor.email if obj.actor else "Sistema"
