from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import logout

from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from ...models.index import Usuario
from ...serializers.index import UsuarioSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"message": "Logout exitoso"}, status=200)
