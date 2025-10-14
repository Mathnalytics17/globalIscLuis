from django.urls import path, include
from .api import ApiRoot
from rest_framework_simplejwt.views import TokenRefreshView
from apps.users.api.views.user.index import (
    UserRegistrationView, LoginAV,
    UserViewSet, EmailVerificationView, UserDetailView,
    ForgotPasswordView, PasswordResetConfirmView, CurrentUserView)
from apps.misc.api.views.companies.index import EmpresaViewSet
from apps.misc.api.views.roles.index import RolViewSet
from apps.activesTree.api.views.index import MaquinaViewSet, SyncCompanyRootFolders,FolderViewSet, AnalisisLubricanteViewSet, ResultadoMuestrasAceiteViewSet
from apps.activesTree.api.views.activesTree.index import ActivesTreeViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.misc.api.views.lubricante.index import LubricanteViewSet
from apps.misc.api.views.pruebas.index import PruebaViewSet
from apps.muestras.api.views.muestras.index import MuestraViewSet, MuestraViewSetList
from apps.muestras.api.views.ingresoLab.index import IngresoLabViewSet
from apps.muestras.api.views.pruebaMuestra.index import PruebaMuestraViewSet
from apps.reporte.api.views.index import ReporteViewSet

from apps.misc.api.views.tipoEquipo.index import TipoEquipoViewSet,ReferenciaEquipoViewSet
from apps.misc.api.views.extraField.index import ExtraFieldViewSet
from apps.misc.api.views.limitesyaux.index import TiposCalidadRetrieveUpdateDestroyView,TipoCalidadView,TipoViscosidadView,AsignarLimitePruebaView,PruebaLimiteViewSet,LimiteGenericosListCreateView,LimiteGenericosRetrieveUpdateDestroyView,ElementoAnalisisViewSet,LimiteCalidadListCreateView,LimiteCalidadRetrieveUpdateDestroyView,LimiteViscosidadListCreateView,LimiteViscosidadRetrieveUpdateDestroyView
from apps.misc.api.views.more.index import get_all_content_types,content_type_detail,SistemaFiltracionDetailView,SistemaFiltracionListCreateView,MarcaGrasaListCreateView,MarcaGrasaRetrieveUpdateDestroyView,MarcaRetrieveUpdateDestroyView,MarcaListCreateView,CalidadListCreateView,CalidadRetrieveUpdateDestroyView,ColorGrasaListCreateView,ColorGrasaRetrieveUpdateDestroyView,ColorListCreateView,ColorRetrieveUpdateDestroyView,NLGIRetrieveUpdateDestroyView,NLGIListCreateView,JabonListCreateView,JabonRetrieveUpdateDestroyView,ComentarioPredefinidoListCreateView,ComentarioPredefinidoRetrieveUpdateDestroyView
from apps.reporte.api.views.index import ReporteViewSet


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
    
    path('activeTree/', EmpresaViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='activeTrees-list'),
    
    
    path('companies/', EmpresaViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='companies-list'),
    path('companies/<int:pk>/', EmpresaViewSet.as_view({ 'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',}), name='companies-list'),
    
    path('folders/', FolderViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='folder-list'),
        path('extraFields/', ExtraFieldViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='folder-list'),
    
    path('folders/<int:pk>/', FolderViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name='folder-detail'),
    
    
    
    
    ##MAQUINAS
    path('machines/', maquina_viewset, name='maquina-list'),
    path('machines/<int:pk>/', maquina_detail_viewset, name='maquina-detail'),
    path('machines/<int:pk>/cambiar_aceite/', MaquinaViewSet.as_view({'post': 'cambiar_aceite'}), name='maquina-cambiar-aceite'),
    path('machines/maquinas_recientes/', MaquinaViewSet.as_view({'get': 'maquinas_recientes'}), name='maquina-recientes'),
    
    
     path('actives-tree/basic-structure/', 
         ActivesTreeViewSet.as_view({'get': 'basic_structure'}), 
         name='basic-structure'),
    
    path('actives-tree/flat-structure/', 
         ActivesTreeViewSet.as_view({'get': 'flat_structure'}), 
         name='flat-structure'),

    
     path('sync-company-roots/', SyncCompanyRootFolders.as_view(), name='sync-company-roots'),
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
    
    
    
    ###LUBRICANTES
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
    
    
    
    ##PRUEBAS
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
    
 
 
 ##MUESTRAS
    path('lubrication/samples/', MuestraViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='muestras-list'),
    
    path('lubrication/samples-list/', MuestraViewSetList.as_view({
        'get': 'list',
        'post': 'create'
    }), name='muestras-list'),
    path('lubrication/samples/<str:pk>/', MuestraViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='muestra-detail'),
    
    
    
    
    ###INGRESO A LABORATORIO
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

path('lubrication/sample-tests/<str:pk>/', PruebaMuestraViewSet.as_view({
    'get': 'retrieve', 
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
}), name='prueba-muestra-detail'),
    
    path('lubrication/sample-tests/by-sample/<str:muestra_id>/', 
     PruebaMuestraViewSet.as_view({'get': 'by_sample'}), 
     name='pruebas-muestra-by-sample'),
    
    

    

    
    path('elementos/', ElementoAnalisisViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='elementos-analisis-list'),
    path('elementos/<int:pk>/', ElementoAnalisisViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='elemento-analisis-detail'),
    
    
    
    
    
    ##REPORTES
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
    
     
    # NUEVOS ENDPOINTS SIGUIENDO TU ESTRUCTURA
    path('lubrication/reports/imprimir_reporte/', ReporteViewSet.as_view({
        'get': 'imprimir_reporte'
    }), name='imprimir-reporte'),
    
    path('lubrication/reports/enviar_correo_reporte/', ReporteViewSet.as_view({
        'post': 'enviar_correo_reporte'
    }), name='enviar-correo-reporte'),
     
      # URL específica para upload signature
    path('upload/signature/', ReporteViewSet.as_view({'post': 'upload_signature'}), name='upload-signature'),
    path('get_signature/', ReporteViewSet.as_view({'post': 'upload_signature'}), name='upload-signature'),

    
    ####LIMITES
    
     # Límites de Viscosidad
    path('limites-viscosidad/', LimiteViscosidadListCreateView.as_view(), name='limiteviscosidad-list'),
    path('limites-viscosidad/<int:pk>/', LimiteViscosidadRetrieveUpdateDestroyView.as_view(), name='limiteviscosidad-detail'),
    
    # Límites de Calidad
    path('limites-calidad/', LimiteCalidadListCreateView.as_view(), name='limitecalidad-list'),
    path('limites-calidad/<int:pk>/', LimiteCalidadRetrieveUpdateDestroyView.as_view(), name='limitecalidad-detail'),
    
    #Limites Genericos
    path('limites-genericos/', LimiteGenericosListCreateView.as_view(), name='limitegenerico-list'),
    path('limites-genericos/<int:pk>/', LimiteGenericosRetrieveUpdateDestroyView.as_view(), name='limitegenerico-detail'),
    

    # urls.py - Agregar estas rutas
    path('prueba-limites/', PruebaLimiteViewSet.as_view({'get': 'list', 'post': 'create'}), name='pruebalimite-list'),
    path('prueba-limites/<int:pk>/', PruebaLimiteViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='pruebalimite-detail'),
    
    
    
    path('pruebas/<int:prueba_id>/asignar-limite/', AsignarLimitePruebaView.as_view(), name='asignar-limite-prueba'),
    path('pruebas/<int:pk>/limite-asignado/',PruebaViewSet.as_view({'get': 'limite_asignado'}), name='limite-asignado'),
    path('tipos-viscosidad/', TipoViscosidadView.as_view({'get': 'list', 'post': 'create'}), name='tipo-viscosidad-list'),
    
    
    
    
    # Calidades
    path('calidades/',CalidadListCreateView.as_view(), name='calidad-list'),
    path('calidades/<int:pk>/', CalidadRetrieveUpdateDestroyView.as_view(), name='calidad-detail'),
    path('tipos-calidad/', TipoCalidadView.as_view({'get': 'list', 'post': 'create'}), name='tipo-viscosidad-list'),
    path('tipos-calidad/<int:pk>/', TiposCalidadRetrieveUpdateDestroyView.as_view(), name='tiposcalidad-detail'),
    
    
 
    path('lubrication/reports/<int:pk>/approve/', ReporteViewSet.as_view({
        'post': 'aprobar'
    }), name='reporte-aprobar'),
    path('lubrication/reports/<int:pk>/send-approval/',ReporteViewSet.as_view({
        'post': 'enviar_aprobacion'
    }), name='reporte-enviar-aprobacion'),
     # Marcas
    path('marcas/', MarcaListCreateView.as_view(), name='marca-list'),
    path('marcas/<int:pk>/', MarcaRetrieveUpdateDestroyView.as_view(), name='marca-detail'),

    
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
    
   

    path('sistemas-filtracion/', SistemaFiltracionListCreateView.as_view(), name='sistemas-filtracion-list'),
    path('sistemas-filtracion/<int:pk>/', SistemaFiltracionDetailView.as_view(), name='sistemas-filtracion-detail'),

   
    # O con DRF:
    path('content/<int:pk>/', content_type_detail, name='content-type-detail'),
    path('content/', get_all_content_types, name='all-content-types'),
    

]