# profiles/api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.urls import reverse_lazy

class ApiRoot(APIView):
    def get(self, request, format=None):
        return Response({

            'users': request.build_absolute_uri(reverse_lazy('user-list')),
            'companies': request.build_absolute_uri(reverse_lazy('companies-list')),
            'roles': request.build_absolute_uri(reverse_lazy('roles-list')),
            'machines': request.build_absolute_uri(reverse_lazy('Maquina-list')),
            'folders': request.build_absolute_uri(reverse_lazy('folder-list')),
            'oilAnalysis': request.build_absolute_uri(reverse_lazy('OilAnalysis-list')),
            'resultsOilAnalysis': request.build_absolute_uri(reverse_lazy('ResultOilAnalysis-list')),
            
        })