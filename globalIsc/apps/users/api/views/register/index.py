from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ...models.index import Usuario
from ...serializers.index import UsuarioSerializer

class RegisterView(APIView):
    def post(self, request):
        serializer = UsuarioSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({'user': serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
