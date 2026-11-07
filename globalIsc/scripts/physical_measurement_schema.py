"""Canonical, reviewable schema for historical physical measurements."""

# source column, stable API acronym, test label, unit, component data type
PHYSICAL_MEASUREMENTS = (
    ("Apariencia", "APARIENCIA", "Apariencia", "", "texto"),
    ("Olor", "OLOR", "Olor", "", "texto"),
    ("Viscosidad Cinemática 40° C", "VISCOSIDAD_40C", "Viscosidad cinemática a 40 °C", "cSt", "numerico"),
    ("Viscosidad Cinemática 100° C", "VISCOSIDAD_100C", "Viscosidad cinemática a 100 °C", "cSt", "numerico"),
    ("Índice de Viscosidad", "INDICE_VISCOSIDAD", "Índice de viscosidad", "", "numerico"),
    ("Punto de Chispa", "PUNTO_CHISPA", "Punto de chispa", "°C", "numerico"),
    ("Densidad @15°C", "DENSIDAD_15C", "Densidad a 15 °C", "g/cm³", "numerico"),
    ("Nitración", "NITRACION", "Nitración", "A/cm", "numerico"),
    ("Oxidación", "OXIDACION", "Oxidación", "A/cm", "numerico"),
    ("Hollín", "HOLLIN", "Hollín", "%", "numerico"),
    ("Sulfatación", "SULFATACION", "Sulfatación", "A/cm", "numerico"),
    ("TAN", "TAN", "Número ácido total", "mg KOH/g", "numerico"),
    ("TBN", "TBN", "Número básico total", "mg KOH/g", "numerico"),
    ("Agua", "AGUA", "Agua", "ppm", "numerico"),
)

# ISO 4406 is deliberately a compound test.  The source column is a compact
# laboratory code (for example ``23/21/17``), but the application receives
# three independent numeric components: 4 µm, 6 µm and 14 µm.
COMPOUND_PHYSICAL_MEASUREMENTS = (
    ("Nivel de Contaminacion", "NIVEL_CONTAMINACION", "Nivel de contaminación", "ISO 4406", ("4um", "6um", "14um")),
)
