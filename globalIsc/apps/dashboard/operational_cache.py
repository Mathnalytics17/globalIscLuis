"""Short-lived cache for the Global Oil operational center."""

from hashlib import sha256
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import connections


VERSION_KEY = "dashboard:operational:center:version"
TIMEOUT_SECONDS = 20


def _in_transaction():
    return connections["default"].in_atomic_block


def _version():
    try:
        value = cache.get(VERSION_KEY)
        if value is None:
            cache.add(VERSION_KEY, 1, timeout=None)
            value = cache.get(VERSION_KEY, 1)
        return int(value)
    except Exception:
        return None


def _key(request, version):
    params = urlencode(sorted((key, value) for key, values in request.query_params.lists() for value in values))
    raw = f"{request.user.pk}|{request.path}|{params}|{version}"
    return f"dashboard:operational:center:{sha256(raw.encode('utf-8')).hexdigest()}"


def get_operational_center(request):
    if _in_transaction():
        return None, None
    version = _version()
    if version is None:
        return None, None
    try:
        return cache.get(_key(request, version)), version
    except Exception:
        return None, version


def set_operational_center(request, payload, version):
    if _in_transaction() or version is None or _version() != version:
        return
    try:
        cache.set(_key(request, version), payload, timeout=TIMEOUT_SECONDS)
    except Exception:
        pass


def invalidate_operational_center():
    try:
        if not cache.add(VERSION_KEY, 1, timeout=None):
            cache.incr(VERSION_KEY)
    except Exception:
        pass
