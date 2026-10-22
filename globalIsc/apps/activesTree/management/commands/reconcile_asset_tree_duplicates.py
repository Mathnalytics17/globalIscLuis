from django.core.management.base import BaseCommand

from apps.activesTree.services import reconcile_duplicate_machine_tree_nodes


class Command(BaseCommand):
    help = (
        "Detecta nodos visuales duplicados para una misma máquina en el árbol "
        "de activos. Use --apply para fusionarlos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Reubica los hijos y elimina los nodos visuales duplicados.",
        )

    def handle(self, *args, **options):
        summary = reconcile_duplicate_machine_tree_nodes(apply=options["apply"])
        action = "Reparación aplicada" if options["apply"] else "Vista previa"
        self.stdout.write(
            f"{action}: {summary['duplicated_machines']} máquina(s) duplicada(s), "
            f"{summary['merged_nodes']} nodo(s) a fusionar."
        )
        for detail in summary["details"]:
            self.stdout.write(
                "  Máquina {machine_id}: conservar nodo {kept_node_id}; "
                "fusionar {removed_node_ids}.".format(**detail)
            )
