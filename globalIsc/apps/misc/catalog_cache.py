"""Safe response caching for technical catalog read endpoints.

Catalogs are read repeatedly while forms and result-entry screens load.  Their
data changes far less frequently than samples/results, so they are suitable for
a short Redis cache.  Keys include the authenticated user and all query
parameters; a global version makes invalidation immediate after a committed
catalog change.  Cache failures deliberately fall back to PostgreSQL.
"""

from hashlib import sha256
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import connections
from rest_framework.response import Response


CATALOG_VERSION_KEY = "misc:catalogs:version"
CATALOG_TIMEOUT_SECONDS = 300


def _transaction_in_progress():
    """Never serve or populate cache while the current DB state is uncommitted."""
    return connections["default"].in_atomic_block


def _version():
    try:
        version = cache.get(CATALOG_VERSION_KEY)
        if version is None:
            cache.add(CATALOG_VERSION_KEY, 1, timeout=None)
            version = cache.get(CATALOG_VERSION_KEY, 1)
        return int(version)
    except Exception:
        return None


def _key(request, version):
    params = urlencode(sorted((key, value) for key, values in request.query_params.lists() for value in values))
    raw = f"{request.user.pk}|{request.path}|{params}|{version}"
    return f"misc:catalogs:response:{sha256(raw.encode('utf-8')).hexdigest()}"


def get_catalog_response(request):
    if _transaction_in_progress():
        return None, None
    version = _version()
    if version is None:
        return None, None
    try:
        return cache.get(_key(request, version)), version
    except Exception:
        return None, version


def set_catalog_response(request, payload, version):
    if _transaction_in_progress() or version is None or _version() != version:
        return
    try:
        cache.set(_key(request, version), payload, timeout=CATALOG_TIMEOUT_SECONDS)
    except Exception:
        pass


def invalidate_catalog_cache():
    try:
        if not cache.add(CATALOG_VERSION_KEY, 1, timeout=None):
            cache.incr(CATALOG_VERSION_KEY)
    except Exception:
        pass


class CatalogResponseCacheMixin:
    """Cache only GET list responses after permissions have been checked."""

    def list(self, request, *args, **kwargs):
        cached_payload, version = get_catalog_response(request)
        if cached_payload is not None:
            return Response(cached_payload)
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            set_catalog_response(request, response.data, version)
        return response
