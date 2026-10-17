from django.urls import path

from .views.activesTree.index import ActivesTreeViewSet
from .views.index import (
    AsignacionPuntoMuestreoViewSet,
    FolderViewSet,
    MaquinaViewSet,
    LubricanteViewSet,
    PuntoMuestreoViewSet,
)


urlpatterns = [
    path("folders/", FolderViewSet.as_view({"get": "list", "post": "create"}), name="folder-list"),
    path("folders/<int:pk>/", FolderViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="folder-detail"),
    path("machines/", MaquinaViewSet.as_view({"get": "list", "post": "create"}), name="maquina-list"),
    path("machines/<int:pk>/", MaquinaViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="maquina-detail"),
    path("machines/<int:pk>/activity/", MaquinaViewSet.as_view({"get": "activity"}), name="maquina-activity"),
    path("machines/<int:pk>/history/", MaquinaViewSet.as_view({"get": "history"}), name="maquina-history"),
    path("machines/<int:pk>/reactivate/", MaquinaViewSet.as_view({"post": "reactivate"}), name="maquina-reactivate"),
    path("sampling-points/", PuntoMuestreoViewSet.as_view({"get": "list", "post": "create"}), name="sampling-points-list"),
    path("sampling-points/<int:pk>/", PuntoMuestreoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="sampling-points-detail"),
    path("sampling-points/<int:pk>/activity/", PuntoMuestreoViewSet.as_view({"get": "activity"}), name="sampling-point-activity"),
    path("sampling-points/<int:pk>/organize/", PuntoMuestreoViewSet.as_view({"post": "organize"}), name="sampling-points-organize"),
    path("sampling-points/<int:pk>/reactivate/", PuntoMuestreoViewSet.as_view({"post": "reactivate"}), name="sampling-points-reactivate"),
    path("lubricants/", LubricanteViewSet.as_view({"get": "list", "post": "create"}), name="lubricant-list"),
    path("lubricants/<int:pk>/", LubricanteViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="lubricant-detail"),
    path("sampling-point-assignments/", AsignacionPuntoMuestreoViewSet.as_view({"get": "list"}), name="sampling-point-assignments-list"),
    path("actives-tree/basic-structure/", ActivesTreeViewSet.as_view({"get": "basic_structure"}), name="basic-structure"),
]
