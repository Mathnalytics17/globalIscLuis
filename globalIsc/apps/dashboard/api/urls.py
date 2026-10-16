from django.urls import path

from .views.index import OperationalCenterViewSet


urlpatterns = [
    path("dashboard/operational-center/", OperationalCenterViewSet.as_view({"get": "list"}), name="operational-center"),
]
