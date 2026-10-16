"""Carga segura de activos desde el Diario de Laboratorio.

Solo crea/reutiliza Maquina, PuntoMuestreo y Lubricante. Nunca crea muestras,
lotes, resultados ni empresas. Ejecutar dentro del contenedor backend.
"""
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import django
from openpyxl import load_workbook

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.api.models.index import Carpeta, Lubricante, PuntoMuestreo


UNKNOWN = {'', 'DESCONOCIDO', 'DESCONOCIDA', 'NO APLICA', 'N.R.', 'N/A', 'NAN'}
KNOWN_BRANDS = {'PETROBRAS', 'MAXFLUID', 'MAXGEAR', 'MAXDIESEL', 'MAXSPEED', 'MOBIL', 'ULTREK', 'GLOBAL'}


def text(value):
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def key(value):
    return ''.join(
        char for char in unicodedata.normalize('NFD', text(value).upper())
        if unicodedata.category(char) != 'Mn'
    )


def usable(value):
    return key(value) not in UNKNOWN


def product_parts(value):
    value = text(value)
    first = key(value).split(' ', 1)[0]
    if first in KNOWN_BRANDS:
        return first.title() if first != 'MAXGEAR' else 'Maxgear', text(value[len(value.split(' ', 1)[0]):])
    # El archivo tiene aceites genéricos; conservarlos sin inventar fabricante.
    return 'Sin fabricante', value


def asset_parts(equipment):
    raw = text(equipment)
    normalized = key(raw)
    draga = re.search(r'DRAGA\s*(?:NO\.?|NUMERO)?\s*(\d+)', normalized)
    unit = re.search(r'\bUG\s*(\d+)\b', normalized)
    excavator = re.search(r'EXCAVADORA\s*(\d+)', normalized)
    boat = re.search(r'LANCHA\s*#?\s*(\d+)', normalized)
    if draga:
        machine = f'DRAGA {draga.group(1)}'
    elif unit:
        machine = f'UNIDAD DE GENERACIÓN {unit.group(1)}'
    elif excavator:
        machine = f'EXCAVADORA {excavator.group(1)}'
    elif boat:
        machine = f'LANCHA {boat.group(1)}'
    else:
        machine = raw

    point = raw
    # Quita únicamente la denominación de máquina cuando el registro trae
    # "DRAGA n - punto" o "punto DRAGA n". Si no, preserva el texto completo.
    point = re.sub(r'^\s*(?:DRAGA\s*(?:NO\.?|NUMERO)?\s*\d+|UNIDAD\s+DE\s+GENERACI[ÓO]N\s*\d+)\s*[-,]\s*', '', point, flags=re.I)
    point = re.sub(r'\s+DRAGA\s*(?:NO\.?|NUMERO)?\s*\d+\s*$', '', point, flags=re.I)
    point = re.sub(r'\s+UG\s*\d+\s*$', '', point, flags=re.I)
    point = text(point) or 'Punto general'
    return machine, point


def numeric_period(value):
    match = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(?:HR|HORA|HORAS)\b', key(value))
    return int(float(match.group(1).replace(',', '.'))) if match else None


def main(path):
    company = Empresa.objects.filter(nombre__iexact='Mineros S.A').first()
    if not company:
        raise SystemExit('No existe la empresa destino Mineros S.A.')

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook['Listado']
    headers = {text(cell.value): index for index, cell in enumerate(next(sheet.iter_rows(min_row=5, max_row=5, values_only=False)))}
    required = ('Cliente', 'Equipo', 'Placa', 'Lubricante', 'Periodo de Servicio')
    missing = [name for name in required if name not in headers]
    if missing:
        raise SystemExit(f'No se encontraron columnas: {missing}')

    records = []
    for row in sheet.iter_rows(min_row=6, values_only=True):
        client = text(row[headers['Cliente']])
        equipment = text(row[headers['Equipo']])
        lubricant = text(row[headers['Lubricante']])
        if key(client) != 'MINEROS ALUVIAL S.A.S' or not usable(equipment) or not usable(lubricant):
            continue
        machine, point = asset_parts(equipment)
        records.append({
            'machine': machine, 'point': point, 'plate': text(row[headers['Placa']]),
            'lubricant': lubricant, 'period': numeric_period(row[headers['Periodo de Servicio']]),
        })

    by_point = defaultdict(list)
    for record in records:
        by_point[(key(record['machine']), key(record['point']))].append(record)

    created = Counter()
    with transaction.atomic():
        root = Carpeta.objects.filter(compania=company, typeFolder='root', id_parent_node='-1').first()
        if not root:
            raise SystemExit(f'La empresa {company.nombre} no tiene carpeta raíz en el árbol.')
        lubricants = {}
        for record in records:
            manufacturer, reference = product_parts(record['lubricant'])
            identity = (key(manufacturer), key(reference))
            if identity in lubricants:
                continue
            item = Lubricante.objects.filter(fabricante__iexact=manufacturer, referencia__iexact=reference).first()
            if not item:
                item = Lubricante.objects.create(fabricante=manufacturer, referencia=reference, nombre=f'{manufacturer} {reference}')
                created['lubricants'] += 1
            lubricants[identity] = item

        machines = {}
        for record in records:
            identity = key(record['machine'])
            if identity in machines:
                continue
            code = record['plate'] if usable(record['plate']) else None
            machine = Maquina.objects.filter(empresa=company, nombre__iexact=record['machine']).first()
            if not machine and code:
                machine = Maquina.objects.filter(empresa=company, codigo_equipo__iexact=code).first()
            if not machine:
                machine = Maquina.objects.create(empresa=company, nombre=record['machine'], codigo_equipo=code)
                created['machines'] += 1
            machines[identity] = machine

        for (_, _), rows in by_point.items():
            # Mantiene el lubricante más repetido en el histórico y el periodo
            # horario más repetido como frecuencia de cambio, si existe.
            exemplar = rows[0]
            lubricant_value = Counter(key(row['lubricant']) for row in rows).most_common(1)[0][0]
            lubricant_row = next(row for row in rows if key(row['lubricant']) == lubricant_value)
            manufacturer, reference = product_parts(lubricant_row['lubricant'])
            catalog = lubricants[(key(manufacturer), key(reference))]
            periods = [row['period'] for row in rows if row['period'] is not None]
            frequency = Counter(periods).most_common(1)[0][0] if periods else None
            machine = machines[key(exemplar['machine'])]
            point = PuntoMuestreo.objects.filter(maquina=machine, nombre__iexact=exemplar['point'], activo=True).first()
            if not point:
                PuntoMuestreo.objects.create(
                    maquina=machine, nombre=exemplar['point'], lubricante_catalogo=catalog,
                    lubricante=catalog.nombre, frecuencia_cambio=frequency,
                    unidad_frecuencia_cambio='horas',
                )
                created['points'] += 1

        # El árbol no deriva sus nodos de Maquina: cada máquina necesita su
        # carpeta-enlace. Se agregan solo las que todavía no tienen ubicación,
        # como hijas directas de la raíz de la empresa para que el usuario pueda
        # moverlas luego a la carpeta organizativa que prefiera.
        for machine in machines.values():
            if not Carpeta.objects.filter(machine=machine).exists():
                Carpeta.objects.create(
                    nombre=machine.nombre,
                    typeFolder='machine',
                    compania=company,
                    id_parent_node=str(root.id),
                    isMachine=True,
                    machine=machine,
                )
                created['machine_tree_nodes'] += 1

    print({
        'source_rows_used': len(records), 'destination_company': company.nombre,
        'created_lubricants': created['lubricants'], 'created_machines': created['machines'],
        'created_sampling_points': created['points'], 'created_machine_tree_nodes': created['machine_tree_nodes'],
        'skipped_unknown_or_not_applicable': 325 - len(records),
    })


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Uso: python scripts/import_lab_assets.py /ruta/archivo.xlsx')
    main(sys.argv[1])
