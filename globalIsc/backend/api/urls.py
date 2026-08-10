from django.urls import include, path

from .api import ApiRoot


urlpatterns = [
    path("", ApiRoot.as_view(), name="api-root"),
    path("", include("apps.users.api.urls")),
    path("", include("apps.dashboard.api.urls")),
    path("", include("apps.misc.api.urls")),
    path("", include("apps.activesTree.api.urls")),
    path("", include("apps.muestras.api.urls")),
    path("", include("apps.resultado.api.urls")),
    path("", include("apps.reporte.api.urls")),
]
