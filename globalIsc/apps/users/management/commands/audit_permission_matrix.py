"""Comprueba que los permisos usados por las vistas estén en la matriz base."""

from __future__ import annotations

import ast
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.users.api.models.index import SecurityPermission
from apps.users.api.services import DEFAULT_PERMISSION_MATRIX


MAPPED_PERMISSION_ATTRIBUTES = {"permission_action_map", "permission_by_action"}
DIRECT_PERMISSION_ATTRIBUTES = {
    "required_permission",
    "default_read_permission",
    "default_write_permission",
}


def _permission_strings(node: ast.AST) -> set[str]:
    """Extract dotted permission codes from a literal or literal collection."""
    values: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and "." in child.value:
            values.add(child.value)
    return values


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: set[str] = set()
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
    return names


def discover_view_permissions(project_root: Path) -> set[str]:
    """Find static permission declarations in API view modules."""
    permissions: set[str] = set()
    for path in project_root.glob("apps/**/api/views/**/*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = _assigned_names(node)
                value = node.value
                if value is None:
                    continue
                if names & (MAPPED_PERMISSION_ATTRIBUTES | DIRECT_PERMISSION_ATTRIBUTES):
                    permissions.update(_permission_strings(value))

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "check_security_permission":
                permissions.update(_permission_strings(node))
    return permissions


class Command(BaseCommand):
    help = "Audita que las acciones protegidas de las vistas existan en la matriz de permisos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            action="store_true",
            help="También comprueba que los permisos definidos ya fueron sincronizados a la base de datos.",
        )

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parents[4]
        used_codes = discover_view_permissions(project_root)
        matrix_codes = {code for _, _, code, _ in DEFAULT_PERMISSION_MATRIX}
        missing_from_matrix = sorted(used_codes - matrix_codes)

        self.stdout.write(f"Acciones protegidas detectadas: {len(used_codes)}")
        self.stdout.write(f"Permisos definidos en la matriz: {len(matrix_codes)}")

        if missing_from_matrix:
            raise CommandError(
                "Acciones usadas por las vistas que no están en DEFAULT_PERMISSION_MATRIX: "
                + ", ".join(missing_from_matrix)
            )

        if options["database"]:
            database_codes = set(SecurityPermission.objects.values_list("code", flat=True))
            missing_from_database = sorted(matrix_codes - database_codes)
            if missing_from_database:
                raise CommandError(
                    "Permisos de la matriz ausentes en la base de datos: "
                    + ", ".join(missing_from_database)
                )
            self.stdout.write(self.style.SUCCESS("La matriz también está sincronizada con la base de datos."))

        self.stdout.write(self.style.SUCCESS("Matriz de permisos completa para las acciones detectadas."))
