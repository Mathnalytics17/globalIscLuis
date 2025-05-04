from django.urls import path, include
from .api import ApiRoot
from rest_framework_simplejwt.views import TokenRefreshView
from apps.users.api.views.user.index import (
    UserRegistrationView, LoginAV,
    UserViewSet, EmailVerificationView, UserDetailView,
    ForgotPasswordView, PasswordResetConfirmView, CurrentUserView)
from apps.misc.api.views.companies.index import EmpresaViewSet
from apps.misc.api.views.roles.index import RolViewSet
from apps.activesTree.api.views.index import MaquinaViewSet, FolderViewSet, AnalisisLubricanteViewSet, ResultadoMuestrasAceiteViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.misc.api.views.lubricante.index import LubricanteViewSet
from apps.misc.api.views.pruebas.index import PruebaViewSet,RelacionPruebaLimiteViewSet
from apps.muestras.api.views.muestras.index import MuestraViewSet
from apps.muestras.api.views.ingresoLab.index import IngresoLabViewSet
from apps.muestras.api.views.pruebaMuestra.index import PruebaMuestraViewSet
from apps.reporte.api.views.index import ReporteViewSet
from apps.resultado.api.views.index import ResultadoViewSet
from apps.misc.api.views.tipoEquipo.index import TipoEquipoViewSet,ReferenciaEquipoViewSet
from apps.misc.api.views.limitesyaux.index import ElementoAnalisisViewSet,LimiteCalidadListCreateView,LimiteCalidadRetrieveUpdateDestroyView,LimiteViscosidadListCreateView,LimiteViscosidadRetrieveUpdateDestroyView
from apps.misc.api.views.more.index import get_all_content_types,content_type_detail,SistemaFiltracionDetailView,SistemaFiltracionListCreateView,MarcaGrasaListCreateView,MarcaGrasaRetrieveUpdateDestroyView,MarcaRetrieveUpdateDestroyView,MarcaListCreateView,CalidadListCreateView,CalidadRetrieveUpdateDestroyView,ColorGrasaListCreateView,ColorGrasaRetrieveUpdateDestroyView,ColorListCreateView,ColorRetrieveUpdateDestroyView,NLGIRetrieveUpdateDestroyView,NLGIListCreateView,JabonListCreateView,JabonRetrieveUpdateDestroyView,ComentarioPredefinidoListCreateView,ComentarioPredefinidoRetrieveUpdateDestroyView
# Configuración de ViewSets para Máquinas
maquina_viewset = MaquinaViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

maquina_detail_viewset = MaquinaViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})


# Repetir este patrón para todos los ViewSets del sistema de lubricantes...

urlpatterns = [
    # API Root
    path('', ApiRoot.as_view(), name='api-root'),
    
    # Autenticación y usuarios
    path('users/', UserViewSet.as_view({'get': 'list'}), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('users/register/', UserRegistrationView.as_view(), name='register'),
    path('users/login/', LoginAV.as_view(), name='token_obtain_pair'),
    path('users/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/verify-email/', EmailVerificationView.as_view(), name='verify_email'),
    path('users/password-reset/', ForgotPasswordView.as_view(), name='password_reset'),
    path('users/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),
    
    # Árbol de activos
    path('companies/', EmpresaViewSet.as_view({'get': 'list'}), name='companies-list'),
    
    path('folders/', FolderViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='folder-list'),
    
    path('folders/<int:pk>/', FolderViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name='folder-detail'),
    
    path('machines/', maquina_viewset, name='maquina-list'),
    path('machines/<int:pk>/', maquina_detail_viewset, name='maquina-detail'),
    path('machines/<int:pk>/cambiar_aceite/', MaquinaViewSet.as_view({'post': 'cambiar_aceite'}), name='maquina-cambiar-aceite'),
    path('machines/maquinas_recientes/', MaquinaViewSet.as_view({'get': 'maquinas_recientes'}), name='maquina-recientes'),
    
    path('oilAnalysis/', AnalisisLubricanteViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='oil-analysis-list'),
    
    path('resultsOilAnalysis/', ResultadoMuestrasAceiteViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='result-oil-analysis-list'),
    

    
    path('lubrication/equipment-types/',TipoEquipoViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='tipos-equipo-list'),
    path('lubrication/equipment-types/<int:pk>/', TipoEquipoViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='tipo-equipo-detail'),
    
    path('lubrication/equipment-references/',ReferenciaEquipoViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='referencias-equipo-list'),
    path('lubrication/equipment-references/<int:pk>/',ReferenciaEquipoViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='referencia-equipo-detail'),
    
    path('lubrication/lubricants/', LubricanteViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='lubricantes-list'),
    path('lubrication/lubricants/<int:pk>/', LubricanteViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='lubricante-detail'),
    
    path('lubrication/tests/', PruebaViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='pruebas-list'),
    path('lubrication/tests/<int:pk>/', PruebaViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='prueba-detail'),
    
 
    path('lubrication/samples/', MuestraViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='muestras-list'),
    path('lubrication/samples/<str:pk>/', MuestraViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='muestra-detail'),
    
    path('lubrication/lab-entries/',IngresoLabViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='ingresos-lab-list'),
    path('lubrication/lab-entries/<int:pk>/',IngresoLabViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='ingreso-lab-detail'),
    
    path('lubrication/sample-tests/', PruebaMuestraViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='pruebas-muestra-list'),
    path('lubrication/sample-tests/<int:pk>/', PruebaMuestraViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='prueba-muestra-detail'),
    
    path('lubrication/results/', ResultadoViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='resultados-list'),
    path('lubrication/results/<int:pk>/',ResultadoViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='resultado-detail'),
    path('lubrication/results/<int:pk>/review/', ResultadoViewSet.as_view({
        'post': 'revisar'
    }), name='resultado-revisar'),
    
    path('lubrication/analysis-elements/', ElementoAnalisisViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='elementos-analisis-list'),
    path('lubrication/analysis-elements/<int:pk>/', ElementoAnalisisViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='elemento-analisis-detail'),
    
    path('lubrication/reports/', ReporteViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='reportes-list'),
    path('lubrication/reports/<int:pk>/',ReporteViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='reporte-detail'),
      path('relaciones/', RelacionPruebaLimiteViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='relacion-list'),
      path('relaciones/<int:pk>/', RelacionPruebaLimiteViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='relacion-list'),
    path('lubrication/reports/<int:pk>/approve/', ReporteViewSet.as_view({
        'post': 'aprobar'
    }), name='reporte-aprobar'),
    path('lubrication/reports/<int:pk>/send-approval/',ReporteViewSet.as_view({
        'post': 'enviar_aprobacion'
    }), name='reporte-enviar-aprobacion'),
     # Marcas
    path('marcas/', MarcaListCreateView.as_view(), name='marca-list'),
    path('marcas/<int:pk>/', MarcaRetrieveUpdateDestroyView.as_view(), name='marca-detail'),

    # Calidades
    path('calidades/',CalidadListCreateView.as_view(), name='calidad-list'),
    path('calidades/<int:pk>/', CalidadRetrieveUpdateDestroyView.as_view(), name='calidad-detail'),
    
    # Colores (lubricantes)
    path('colores/', ColorListCreateView.as_view(), name='color-list'),
    path('colores/<int:pk>/', ColorRetrieveUpdateDestroyView.as_view(), name='color-detail'),
    
    # Marcas de Grasa
    path('marcas-grasa/', MarcaGrasaListCreateView.as_view(), name='marcagrasa-list'),
    path('marcas-grasa/<int:pk>/',MarcaGrasaRetrieveUpdateDestroyView.as_view(), name='marcagrasa-detail'),
    
    # NLGI
    path('nlgi/', NLGIListCreateView.as_view(), name='nlgi-list'),
    path('nlgi/<int:pk>/', NLGIRetrieveUpdateDestroyView.as_view(), name='nlgi-detail'),
    
    # Jabones
    path('jabones/', JabonListCreateView.as_view(), name='jabon-list'),
    path('jabones/<int:pk>/', JabonRetrieveUpdateDestroyView.as_view(), name='jabon-detail'),
    
    # Colores de Grasa
    path('colores-grasa/', ColorGrasaListCreateView.as_view(), name='colorgrasa-list'),
    path('colores-grasa/<int:pk>/', ColorGrasaRetrieveUpdateDestroyView.as_view(), name='colorgrasa-detail'),
    
    # Comentarios Predefinidos
    path('comentarios-predefinidos/', ComentarioPredefinidoListCreateView.as_view(), name='comentariopredefinido-list'),
    path('comentarios-predefinidos/<int:pk>/', ComentarioPredefinidoRetrieveUpdateDestroyView.as_view(), name='comentariopredefinido-detail'),
    
    # Límites de Viscosidad
    path('limites-viscosidad/', LimiteViscosidadListCreateView.as_view(), name='limiteviscosidad-list'),
    path('limites-viscosidad/<int:pk>/', LimiteViscosidadRetrieveUpdateDestroyView.as_view(), name='limiteviscosidad-detail'),
    
    # Límites de Calidad
    path('limites-calidad/', LimiteCalidadListCreateView.as_view(), name='limitecalidad-list'),
    path('limites-calidad/<int:pk>/', LimiteCalidadRetrieveUpdateDestroyView.as_view(), name='limitecalidad-detail'),

    path('sistemas-filtracion/', SistemaFiltracionListCreateView.as_view(), name='sistemas-filtracion-list'),
    path('sistemas-filtracion/<int:pk>/', SistemaFiltracionDetailView.as_view(), name='sistemas-filtracion-detail'),

   
    # O con DRF:
    path('content/<int:pk>/', content_type_detail, name='content-type-detail'),
    path('content/', get_all_content_types, name='all-content-types'),
]