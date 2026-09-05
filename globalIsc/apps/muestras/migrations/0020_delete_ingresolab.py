from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("muestras", "0019_pruebamuestra_condicion_catalogo"),
    ]

    operations = [
        migrations.DeleteModel(name="IngresoLab"),
    ]
