from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from ...models.index import Empresa, Rol, Usuario
from apps.users.api.serializers.index import UsuarioSerializer,UserSerializer

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [AllowAny]  # Permite registro sin autenticación

class UserView(APIView):
    permission_classes= [IsAuthenticated]

    def get(selfs,request):
        serializer=UserSerializer(request.user)
        return Response(serializer.data)
