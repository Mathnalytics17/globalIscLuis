"""Sincronización interna de las raíces del árbol de activos."""

from apps.activesTree.api.models.index import Carpeta


def ensure_company_root(company):
    """Cada empresa tiene siempre una raíz, sin requerir una acción de UI."""
    root, created = Carpeta.objects.get_or_create(
        compania=company,
        typeFolder='root',
        id_parent_node='-1',
        defaults={
            'nombre': company.nombre,
            'isMachine': False,
            'is_pt_medida': False,
        },
    )
    if not created and root.nombre != company.nombre:
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
    node = Carpeta.objects.filter(machine=machine).order_by('id').first()
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
