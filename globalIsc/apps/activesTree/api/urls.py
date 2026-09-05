from django.urls import path

from .views.activesTree.index import ActivesTreeViewSet
from .views.index import (
    AsignacionPuntoMuestreoViewSet,
    FolderViewSet,
    MaquinaViewSet,
    PuntoMuestreoViewSet,
    SyncCompanyRootFolders,
)


urlpatterns = [
    path("folders/", FolderViewSet.as_view({"get": "list", "post": "create"}), name="folder-list"),
    path("folders/<int:pk>/", FolderViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="folder-detail"),
    path("machines/", MaquinaViewSet.as_view({"get": "list", "post": "create"}), name="maquina-list"),
    path("machines/<int:pk>/", MaquinaViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="maquina-detail"),
    path("sampling-points/", PuntoMuestreoViewSet.as_view({"get": "list", "post": "create"}), name="sampling-points-list"),
    path("sampling-points/<int:pk>/", PuntoMuestreoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="sampling-points-detail"),
    path("sampling-points/<int:pk>/organize/", PuntoMuestreoViewSet.as_view({"post": "organize"}), name="sampling-points-organize"),
    path("sampling-point-assignments/", AsignacionPuntoMuestreoViewSet.as_view({"get": "list"}), name="sampling-point-assignments-list"),
    path("actives-tree/basic-structure/", ActivesTreeViewSet.as_view({"get": "basic_structure"}), name="basic-structure"),
    path("sync-company-roots/", SyncCompanyRootFolders.as_view(), name="sync-company-roots"),
]
