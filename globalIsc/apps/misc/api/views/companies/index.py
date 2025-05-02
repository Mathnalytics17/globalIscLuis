from rest_framework import viewsets

from ...models.companies.index import Empresa
from ...serializers.companies.index import EmpresaSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated

class EmpresaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # Acceso público sin autenticación
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer

