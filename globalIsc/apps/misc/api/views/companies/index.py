from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from ...models.companies.index import Empresa
from ...serializers.companies.index import EmpresaSerializer

class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer

