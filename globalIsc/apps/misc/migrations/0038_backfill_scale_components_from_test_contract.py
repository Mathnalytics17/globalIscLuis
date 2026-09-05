from django.db import migrations
import re
import unicodedata


def _normalize(value):
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _tokens(value):
    return set(_normalize(value).split())


def _single_matching_scale(scales, text):
    text_tokens = _tokens(text)
    matches = []
    for scale in scales:
        candidates = [_normalize(getattr(scale, "codigo", "")), _normalize(getattr(scale, "nombre", ""))]
        scale_tokens = set()
        for candidate in candidates:
            scale_tokens.update(candidate.split())
        scale_tokens.discard("")
        if scale_tokens and scale_tokens.issubset(text_tokens):
            matches.append(scale)
    return matches[0] if len(matches) == 1 else None


def forwards(apps, schema_editor):
    Scale = apps.get_model("misc", "EscalaComparacion")
    Component = apps.get_model("misc", "PruebaResultadoComponente")
    LimitField = apps.get_model("misc", "PruebaLimiteCampo")

    scales = list(Scale.objects.filter(deleted_at__isnull=True, activo=True))

    for component in Component.objects.filter(tipo_dato="escala", escala_comparacion__isnull=True):
        scale = _single_matching_scale(scales, component.nombre)
        if scale:
            component.escala_comparacion_id = scale.id
            component.save(update_fields=["escala_comparacion"])

    for field in LimitField.objects.filter(tipo_comparacion="escala", escala_comparacion__isnull=True).select_related("componente"):
        scale_id = getattr(field.componente, "escala_comparacion_id", None)
        if not scale_id:
            scale = _single_matching_scale(scales, field.nombre)
            scale_id = getattr(scale, "id", None)
        if scale_id:
            field.escala_comparacion_id = scale_id
            field.save(update_fields=["escala_comparacion"])


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0037_cleanup_legacy_limits"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
