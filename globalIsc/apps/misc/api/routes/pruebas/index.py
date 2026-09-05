from django.urls import path

from apps.misc.api.views.pruebas.index import PruebaViewSet

urlpatterns = [
    path("misc/tests/", PruebaViewSet.as_view({"get": "list", "post": "create"})),
    path("misc/tests/<int:pk>/", PruebaViewSet.as_view({
        "get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy",
    })),
    path("misc/tests/<int:pk>/restore/", PruebaViewSet.as_view({"post": "restore"})),
]
