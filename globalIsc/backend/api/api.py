# profiles/api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.urls import reverse_lazy

class ApiRoot(APIView):
    def get(self, request, format=None):
        return Response({
            'users': request.build_absolute_uri(reverse_lazy('user-list')),
            'companies': request.build_absolute_uri(reverse_lazy('companies-list')),
            'security_roles': request.build_absolute_uri(reverse_lazy('security-roles-list')),
            'machines': request.build_absolute_uri(reverse_lazy('maquina-list')),
            'folders': request.build_absolute_uri(reverse_lazy('folder-list')),
            'technical_catalogs': request.build_absolute_uri(reverse_lazy('dynamic-technical-catalogs-list')),
            'sample_batches': request.build_absolute_uri(reverse_lazy('sample-batches-list')),
        })
