"""Django model exports for the laboratory-results bounded context."""

from apps.resultado.api.models.index import (
    HistoricoResultado,
    Resultado,
    RevisionResultado,
    VersionInterpretacion,
)

__all__ = ["HistoricoResultado", "Resultado", "RevisionResultado", "VersionInterpretacion"]
