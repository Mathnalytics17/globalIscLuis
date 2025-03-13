from django.urls import path, include
from .api import ApiRoot
from apps.users.api.views.user.index import UsuarioViewSet, UserView
from apps.misc.api.views.companies.index import EmpresaViewSet
from apps.misc.api.views.roles.index import RolViewSet
from apps.users.api.views.register.index import RegisterView
from apps.users.api.views.login.index import LogoutView
from apps.misc.api.views.companies.index import EmpresaViewSet
from apps.activesTree.api.views.index import MaquinaViewSet,FolderViewSet, AnalisisLubricanteViewSet, ResultadoMuestrasAceiteViewSet


from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
# Crear una instancia del ViewSet para acceder a sus métodos
maquina_viewset = MaquinaViewSet.as_view({
    'get': 'list',           # Listar todas las máquinas
    'post': 'create',        # Crear una nueva máquina
})

maquina_detail_viewset = MaquinaViewSet.as_view({
    'get': 'retrieve',       # Recuperar una máquina específica
    'put': 'update',         # Actualizar una máquina
    'patch': 'partial_update',  # Actualizar parcialmente una máquina
    'delete': 'destroy',     # Eliminar una máquina
})
urlpatterns = [
path('',ApiRoot.as_view(), name='api-root'),
path('users/', UsuarioViewSet.as_view({'get': 'list'}), name='user-list'),
path('auth/me',UserView.as_view(),name='user-detail'),
path('users/register/', RegisterView.as_view(), name='register'),


path('roles/',RolViewSet.as_view({'get': 'list'}),name='roles-list'),

path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
path('logout/', LogoutView.as_view(), name='logout'),

#ARBOL ACTIVOS
path('companies/',EmpresaViewSet.as_view({'get': 'list'}),name='companies-list'),
path('folders/',FolderViewSet.as_view({
    'get': 'list',
    'post': 'create'  # Permite POST para crear carpetas
}),name='folder-list'),
# Rutas para recuperar, actualizar y eliminar una carpeta específica
    path('folders/<int:pk>/', FolderViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name='folder-detail'),
path('machines/',MaquinaViewSet.as_view({'get': 'list','post': 'create' }),name='Maquina-list'),



    # Rutas para recuperar, actualizar y eliminar una máquina específica
    path('machines/<int:pk>/', maquina_detail_viewset, name='maquina-detail'),

    # Ruta para la acción personalizada 'cambiar_aceite'
    path('machines/<int:pk>/cambiar_aceite/', MaquinaViewSet.as_view({'post': 'cambiar_aceite'}), name='maquina-cambiar-aceite'),

    # Ruta para la acción personalizada 'maquinas_recientes'
    path('machines/maquinas_recientes/', MaquinaViewSet.as_view({'get': 'maquinas_recientes'}), name='maquina-recientes'),
path('oilAnalysis/',AnalisisLubricanteViewSet.as_view({'get': 'list','post': 'create' }),name='OilAnalysis-list'),
path('resultsOilAnalysis/',ResultadoMuestrasAceiteViewSet.as_view({'get': 'list','post': 'create' }),name='ResultOilAnalysis-list'),

]