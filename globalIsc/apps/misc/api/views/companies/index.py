from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import models

from ...models.companies.index import Empresa
from apps.misc.api.serializers.companies.index import EmpresaSerializer

class EmpresaViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]  # Acceso público sin autenticación
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer

    # GET /api/empresas/ - Listar todas las empresas
    def list(self, request, *args, **kwargs):
        """
        Lista todas las empresas
        """
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"error": f"Error al listar empresas: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # GET /api/empresas/{id}/ - Obtener una empresa específica
    def retrieve(self, request, *args, **kwargs):
        """
        Obtiene una empresa específica por ID
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Empresa.DoesNotExist:
            return Response(
                {"error": "Empresa no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al obtener empresa: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # POST /api/empresas/ - Crear una nueva empresa
    def create(self, request, *args, **kwargs):
        """
        Crea una nueva empresa
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"error": f"Error al crear empresa: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    # PUT /api/empresas/{id}/ - Actualizar una empresa completa
    def update(self, request, *args, **kwargs):
        """
        Actualiza una empresa completa
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response(serializer.data)
        except Empresa.DoesNotExist:
            return Response(
                {"error": "Empresa no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al actualizar empresa: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    # PATCH /api/empresas/{id}/ - Actualización parcial
    def partial_update(self, request, *args, **kwargs):
        """
        Actualización parcial de una empresa
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response(serializer.data)
        except Empresa.DoesNotExist:
            return Response(
                {"error": "Empresa no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al actualizar empresa: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    # DELETE /api/empresas/{id}/ - Eliminar una empresa
    def destroy(self, request, *args, **kwargs):
        """
        Elimina una empresa
        """
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(
                {"message": "Empresa eliminada correctamente"},
                status=status.HTTP_204_NO_CONTENT
            )
        except Empresa.DoesNotExist:
            return Response(
                {"error": "Empresa no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al eliminar empresa: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Métodos personalizados para acciones adicionales
    def perform_create(self, serializer):
        """
        Lógica adicional al crear una empresa
        """
        serializer.save()

    def perform_update(self, serializer):
        """
        Lógica adicional al actualizar una empresa
        """
        serializer.save()

    def perform_destroy(self, instance):
        """
        Lógica adicional al eliminar una empresa
        """
        instance.delete()

    # Acciones personalizadas adicionales
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas de empresas
        """
        try:
            total_empresas = Empresa.objects.count()
            return Response({
                "total_empresas": total_empresas,
                "ultima_empresa_creada": Empresa.objects.last().nombre if total_empresas > 0 else None
            })
        except Exception as e:
            return Response(
                {"error": f"Error al obtener estadísticas: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def informacion_completa(self, request, pk=None):
        """
        Información completa de una empresa
        """
        try:
            empresa = self.get_object()
            # Aquí puedes agregar más información relacionada si es necesario
            serializer = self.get_serializer(empresa)
            return Response(serializer.data)
        except Empresa.DoesNotExist:
            return Response(
                {"error": "Empresa no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        """
        Buscar empresas por nombre
        """
        try:
            nombre = request.query_params.get('nombre', '')
            if nombre:
                empresas = Empresa.objects.filter(nombre__icontains=nombre)
                serializer = self.get_serializer(empresas, many=True)
                return Response(serializer.data)
            else:
                return Response(
                    {"error": "Parámetro 'nombre' requerido"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {"error": f"Error en la búsqueda: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )