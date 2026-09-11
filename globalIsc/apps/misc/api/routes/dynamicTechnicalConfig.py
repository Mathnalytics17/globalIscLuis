from django.urls import path

from apps.misc.api.views.dynamicTechnicalConfig.index import (
    CatalogoTecnicoViewSet,
    CatalogoTecnicoVersionViewSet,
    CampoTecnicoMuestraViewSet,
    CatalogoTecnicoCampoViewSet,
    CatalogoTecnicoItemViewSet,
    CatalogoTecnicoItemValorViewSet,
    EscalaComparacionItemViewSet,
    EscalaComparacionViewSet,
    PruebaFuenteLimiteViewSet,
    CriterioEvaluacionLimiteViewSet,
    PruebaLimiteCampoViewSet,
)

urlpatterns = [
    path("technical-config/catalogs/", CatalogoTecnicoViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/catalogs/sample-form/", CatalogoTecnicoViewSet.as_view({"get": "sample_form"})),
    path("technical-config/catalogs/<int:pk>/", CatalogoTecnicoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/catalogs/<int:pk>/restore/", CatalogoTecnicoViewSet.as_view({"post": "restore"})),
    path("technical-config/catalog-versions/", CatalogoTecnicoVersionViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/catalog-versions/<int:pk>/", CatalogoTecnicoVersionViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/catalog-versions/<int:pk>/restore/", CatalogoTecnicoVersionViewSet.as_view({"post": "restore"})),

    path("technical-config/sample-fields/", CampoTecnicoMuestraViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/sample-fields/<int:pk>/", CampoTecnicoMuestraViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/sample-fields/<int:pk>/restore/", CampoTecnicoMuestraViewSet.as_view({"post": "restore"})),

    path("technical-config/catalog-fields/", CatalogoTecnicoCampoViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/catalog-fields/<int:pk>/", CatalogoTecnicoCampoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/catalog-fields/<int:pk>/restore/", CatalogoTecnicoCampoViewSet.as_view({"post": "restore"})),

    path("technical-config/catalog-items/", CatalogoTecnicoItemViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/catalog-items/<int:pk>/", CatalogoTecnicoItemViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/catalog-items/<int:pk>/restore/", CatalogoTecnicoItemViewSet.as_view({"post": "restore"})),
    path("technical-config/catalog-items/import-excel/", CatalogoTecnicoItemViewSet.as_view({"post": "import_excel"})),
    path("technical-config/catalog-items/template-excel/", CatalogoTecnicoItemViewSet.as_view({"get": "template_excel"})),

    path("technical-config/catalog-item-values/", CatalogoTecnicoItemValorViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/catalog-item-values/<int:pk>/", CatalogoTecnicoItemValorViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),

    path("technical-config/comparison-scales/", EscalaComparacionViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/comparison-scales/<int:pk>/", EscalaComparacionViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/comparison-scales/<int:pk>/restore/", EscalaComparacionViewSet.as_view({"post": "restore"})),

    path("technical-config/comparison-scale-items/", EscalaComparacionItemViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/comparison-scale-items/reorder/", EscalaComparacionItemViewSet.as_view({"post": "reorder"})),
    path("technical-config/comparison-scale-items/<int:pk>/", EscalaComparacionItemViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/comparison-scale-items/<int:pk>/restore/", EscalaComparacionItemViewSet.as_view({"post": "restore"})),

    path("technical-config/limit-sources/", PruebaFuenteLimiteViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/limit-sources/resolve-preview/", PruebaFuenteLimiteViewSet.as_view({"post": "resolve_preview"})),
    path("technical-config/limit-sources/<int:pk>/generate-fields/", PruebaFuenteLimiteViewSet.as_view({"post": "generate_fields"})),
    path("technical-config/limit-sources/<int:pk>/matrix-template/", PruebaFuenteLimiteViewSet.as_view({"get": "matrix_template"})),
    path("technical-config/limit-sources/<int:pk>/import-matrix/", PruebaFuenteLimiteViewSet.as_view({"post": "import_matrix"})),
    path("technical-config/limit-sources/<int:pk>/", PruebaFuenteLimiteViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/limit-sources/<int:pk>/restore/", PruebaFuenteLimiteViewSet.as_view({"post": "restore"})),

    path("technical-config/limit-fields/", PruebaLimiteCampoViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/limit-fields/<int:pk>/", PruebaLimiteCampoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/limit-fields/<int:pk>/restore/", PruebaLimiteCampoViewSet.as_view({"post": "restore"})),

    path("technical-config/evaluation-criteria/", CriterioEvaluacionLimiteViewSet.as_view({"get": "list", "post": "create"})),
    path("technical-config/evaluation-criteria/<int:pk>/", CriterioEvaluacionLimiteViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    path("technical-config/evaluation-criteria/<int:pk>/restore/", CriterioEvaluacionLimiteViewSet.as_view({"post": "restore"})),

]
