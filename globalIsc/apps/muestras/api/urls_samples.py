from django.urls import path

from apps.muestras.api.views.muestras.index import MuestraViewSet, MuestraViewSetList


urlpatterns = [
    path("lubrication/samples-list/", MuestraViewSetList.as_view({"get": "list"}), name="samples-table-list"),
    path("lubrication/samples/", MuestraViewSet.as_view({"get": "list", "post": "create"}), name="samples-list"),
    path(
        "lubrication/samples/<str:pk>/",
        MuestraViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="samples-detail",
    ),
    path(
        "lubrication/samples/<str:pk>/history/",
        MuestraViewSet.as_view({"get": "history"}),
        name="samples-history",
    ),
    path(
        "lubrication/samples/<str:pk>/invalidate/",
        MuestraViewSet.as_view({"post": "invalidate"}),
        name="samples-invalidate",
    ),
    path(
        "lubrication/samples/<str:pk>/reactivate/",
        MuestraViewSet.as_view({"post": "reactivate"}),
        name="samples-reactivate",
    ),
]
