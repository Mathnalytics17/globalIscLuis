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
