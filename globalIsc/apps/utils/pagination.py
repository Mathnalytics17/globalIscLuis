from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Paginación estándar para tablas del sistema.

    Respuesta DRF:
    {
      "count": N,
      "next": url|null,
      "previous": url|null,
      "results": [...]
    }
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 1000
