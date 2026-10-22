"""Sincronización y saneamiento interno del árbol de activos."""

from collections import defaultdict

from django.db import transaction

from apps.activesTree.api.models.index import Carpeta


def ensure_company_root(company):
    """Cada empresa tiene siempre una raíz, sin requerir una acción de UI."""
    roots = list(Carpeta.objects.filter(
        compania=company,
        typeFolder='root',
        id_parent_node='-1',
    ).order_by('id'))
    if roots:
        root = roots[0]
        # Legacy imports could create more than one root.  A plain
        # get_or_create raises MultipleObjectsReturned here, which used to
        # turn an otherwise valid machine creation into a 500 response.
        for duplicate in roots[1:]:
            Carpeta.objects.filter(id_parent_node=str(duplicate.id)).update(
                id_parent_node=str(root.id)
            )
            duplicate.delete()
    else:
        root = Carpeta.objects.create(
            compania=company,
            typeFolder='root',
            id_parent_node='-1',
            nombre=company.nombre,
            isMachine=False,
            is_pt_medida=False,
        )
    if root.nombre != company.nombre:
        root.nombre = company.nombre
        root.save(update_fields=['nombre'])
    return root


def ensure_active_company_roots():
    from apps.misc.api.models.companies.index import Empresa

    for company in Empresa.objects.filter(is_active=True).only('id', 'nombre'):
        ensure_company_root(company)


def ensure_machine_tree_node(machine):
    """Expose a machine in its company's asset tree without relocating it.

    New machines are placed directly below the company root. If a node already
    exists, its current parent is intentionally preserved: the customer may
    have moved it into a meaningful folder after its initial reception.
    """
    root = ensure_company_root(machine.empresa)
    node = _preferred_machine_node(
        Carpeta.objects.filter(machine=machine).order_by('id'),
        root.id,
    )
    if node:
        return node
    return Carpeta.objects.create(
        nombre=machine.nombre,
        compania=machine.empresa,
        typeFolder='machine',
        id_parent_node=str(root.id),
        isMachine=True,
        is_pt_medida=False,
        machine=machine,
    )


def _preferred_machine_node(nodes, root_id):
    """Keep the intentional location when legacy data has duplicate nodes.

    A folder below a customer-created grouping (for example ``Dragas``) is
    more meaningful than the automatic node placed directly below the company
    root.  That makes the reconciliation deterministic without flattening the
    customer's asset tree.
    """
    nodes = list(nodes)
    if not nodes:
        return None
    return min(
        nodes,
        key=lambda node: (
            str(node.id_parent_node) == str(root_id),
            node.id,
        ),
    )


def reconcile_duplicate_machine_tree_nodes(*, apply=False):
    """Find duplicate visual nodes for a machine and optionally merge them.

    The machine and its sampling points live in their own models, so deleting
    an extra *visual* node does not delete operational data.  Children of an
    obsolete node are first re-parented to the retained node.  Returning a
    summary lets a command run safely in dry-run mode before production repair.
    """
    nodes_by_machine = defaultdict(list)
    for node in Carpeta.objects.exclude(machine__isnull=True).select_related('machine__empresa').order_by('id'):
        nodes_by_machine[node.machine_id].append(node)

    summary = {"duplicated_machines": 0, "merged_nodes": 0, "details": []}
    for machine_id, nodes in nodes_by_machine.items():
        if len(nodes) < 2:
            continue
        machine = nodes[0].machine
        root = ensure_company_root(machine.empresa)
        keep = _preferred_machine_node(nodes, root.id)
        duplicates = [node for node in nodes if node.id != keep.id]
        summary["duplicated_machines"] += 1
        summary["merged_nodes"] += len(duplicates)
        summary["details"].append({
            "machine_id": machine_id,
            "kept_node_id": keep.id,
            "removed_node_ids": [node.id for node in duplicates],
        })
        if not apply:
            continue
        with transaction.atomic():
            for duplicate in duplicates:
                Carpeta.objects.filter(id_parent_node=str(duplicate.id)).update(
                    id_parent_node=str(keep.id)
                )
                duplicate.delete()
    return summary
