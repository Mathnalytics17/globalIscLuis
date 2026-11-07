"""Cache de lectura para la lista de máquinas.

La caché es deliberadamente una optimización opcional: cualquier fallo de
Redis se registra y deja que la vista consulte PostgreSQL normalmente. Las
claves incluyen el usuario y la versión de los activos, por lo que jamás se
comparte una respuesta entre usuarios ni se devuelve una lista previa a una
modificación confirmada.
"""

from hashlib import sha256
import logging
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import connections


logger = logging.getLogger(__name__)

MACHINE_LIST_VERSION_KEY = "actives:machines:list-version"
MACHINE_LIST_TIMEOUT_SECONDS = 120


def _get_version():
    try:
        version = cache.get(MACHINE_LIST_VERSION_KEY)
        if version is None:
            cache.add(MACHINE_LIST_VERSION_KEY, 1, timeout=None)
            version = cache.get(MACHINE_LIST_VERSION_KEY, 1)
        return int(version)
    except Exception:  # Cache must never make the operational API unavailable.
        logger.warning("No fue posible leer la versión de caché de máquinas.", exc_info=True)
        return 0


def machine_list_cache_key(request, version):
    """Build a user-scoped key from all query parameters, in stable order."""
    query = urlencode(sorted((key, value) for key, values in request.query_params.lists() for value in values))
    digest = sha256(query.encode("utf-8")).hexdigest()
    return f"actives:machines:list:v{version}:user:{request.user.pk}:q:{digest}"


def get_machine_list_response(request):
    version = _get_version()
    try:
        return cache.get(machine_list_cache_key(request, version)), version
    except Exception:
        logger.warning("No fue posible leer la caché de lista de máquinas.", exc_info=True)
        return None, version


def set_machine_list_response(request, payload, version):
    try:
        # A write completed while the response was being serialized. Do not
        # populate the new namespace with a response from the old data.
        if _get_version() != version:
            return
        cache.set(machine_list_cache_key(request, version), payload, timeout=MACHINE_LIST_TIMEOUT_SECONDS)
    except Exception:
        logger.warning("No fue posible guardar la caché de lista de máquinas.", exc_info=True)


def invalidate_machine_list_cache():
    """Advance the namespace version after committed changes to active assets."""
    try:
        if not cache.add(MACHINE_LIST_VERSION_KEY, 1, timeout=None):
            cache.incr(MACHINE_LIST_VERSION_KEY)
    except Exception:
        logger.warning("No fue posible invalidar la caché de lista de máquinas.", exc_info=True)


def get_related_read_response(request, namespace):
    """Read cache for machine history, machine samples and the asset tree."""
    if connections["default"].in_atomic_block:
        return None, None
    version = _get_version()
    key = f"actives:{namespace}:v{version}:user:{request.user.pk}:q:{sha256((request.path + '?' + request.META.get('QUERY_STRING', '')).encode('utf-8')).hexdigest()}"
    try:
        return cache.get(key), (key, version)
    except Exception:
        return None, None


def set_related_read_response(payload, token, timeout):
    if not token or connections["default"].in_atomic_block:
        return
    key, version = token
    if _get_version() != version:
        return
    try:
        cache.set(key, payload, timeout=timeout)
    except Exception:
        logger.warning("No fue posible guardar caché de lectura de activos.", exc_info=True)
