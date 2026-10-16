import mimetypes
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, JsonResponse
from django.db.models import Q


PUBLIC_TEMPLATE_ASSETS = {"templates/logo-globaloil.png", "templates/icon-report.png"}


def private_media(request, path):
    """Serve user-generated media only after authenticating and applying tenant scope."""
    normalised = str(PurePosixPath(path))
    if normalised.startswith("/") or ".." in PurePosixPath(normalised).parts:
        raise Http404
    if normalised in PUBLIC_TEMPLATE_ASSETS:
        allowed = True
    elif not request.user.is_authenticated:
        return JsonResponse({"detail": "Autenticación requerida."}, status=401)
    else:
        allowed = normalised in request.session.get("pending_signature_paths", [])
        if not allowed:
            # Imports here avoid coupling the startup of the core project to report models.
            from apps.reporte.api.models.index import Reporte
            from apps.users.api.models.index import User

            reports = Reporte.objects.filter(
                Q(firma_ruta=normalised) | Q(firma_ruta=f"{settings.MEDIA_URL}{normalised}")
            )
            if not (request.user.is_superuser or request.user.role == User.Role.GLOBAL):
                if not request.user.empresa_id:
                    reports = reports.none()
                else:
                    reports = reports.filter(
                        Q(lote__cliente_empresa_id=request.user.empresa_id)
                        | Q(muestra__lote__cliente_empresa_id=request.user.empresa_id)
                    )
            allowed = reports.exists() or normalised == getattr(getattr(request.user, "firma_predeterminada", None), "name", "")
    if not allowed or not default_storage.exists(normalised):
        raise Http404
    content_type, _ = mimetypes.guess_type(normalised)
    return FileResponse(default_storage.open(normalised, "rb"), content_type=content_type or "application/octet-stream")


def csrf_failure(request, reason=""):
    """Never include CSRF diagnostics in the response sent to a browser."""
    return JsonResponse({"detail": "Solicitud de seguridad inválida."}, status=403)
