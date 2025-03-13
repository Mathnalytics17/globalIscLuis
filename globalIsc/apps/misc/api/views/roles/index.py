from rest_framework import viewsets

from ...models.roles.index import Rol
from ...serializers.roles.index import RolSerializer


class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer