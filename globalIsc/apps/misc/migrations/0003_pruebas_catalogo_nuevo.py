# Migración manual para convertir el catálogo viejo de Prueba al catálogo nuevo
# basado en la maqueta de creación de pruebas.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0002_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="prueba",
            old_name="codigo",
            new_name="acronimo",
        ),
        migrations.RenameField(
            model_name="prueba",
            old_name="nombre",
            new_name="nombre_variable",
        ),
        migrations.RenameField(
            model_name="prueba",
            old_name="metodo_referencia",
            new_name="metodo",
        ),
        migrations.RemoveField(
            model_name="prueba",
            name="descripcion",
        ),
        migrations.RemoveField(
            model_name="prueba",
            name="is_subPrueba",
        ),
        migrations.RemoveField(
            model_name="prueba",
            name="parent_node",
        ),
        migrations.RemoveField(
            model_name="prueba",
            name="categoria",
        ),
        migrations.AddField(
            model_name="prueba",
            name="condicion",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="prueba",
            name="equipo",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="prueba",
            name="tiene_submetodos",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="prueba",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prueba",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="prueba",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="prueba",
            name="acronimo",
            field=models.CharField(max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name="prueba",
            name="nombre_variable",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="prueba",
            name="unidad_medida",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name="prueba",
            name="metodo",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AlterModelOptions(
            name="prueba",
            options={"ordering": ["nombre_variable"]},
        ),
        migrations.AddIndex(
            model_name="prueba",
            index=models.Index(fields=["activo"], name="misc_prueba_activo_idx"),
        ),
        migrations.AddIndex(
            model_name="prueba",
            index=models.Index(fields=["acronimo"], name="misc_prueba_acronimo_idx"),
        ),
        migrations.AddIndex(
            model_name="prueba",
            index=models.Index(fields=["nombre_variable"], name="misc_prueba_nomvar_idx"),
        ),
        migrations.CreateModel(
            name="PruebaResultado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=150)),
                ("acronimo", models.CharField(blank=True, max_length=30, null=True)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("activo", models.BooleanField(default=True)),
                ("prueba", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resultados", to="misc.prueba")),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.CreateModel(
            name="PruebaSeparador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("simbolo", models.CharField(max_length=10)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("activo", models.BooleanField(default=True)),
                ("prueba", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="separadores", to="misc.prueba")),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.CreateModel(
            name="PruebaSubmetodo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=150)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("activo", models.BooleanField(default=True)),
                ("prueba", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submetodos", to="misc.prueba")),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.CreateModel(
            name="PruebaDisposicion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=150)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("activo", models.BooleanField(default=True)),
                ("prueba", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="disposiciones", to="misc.prueba")),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.CreateModel(
            name="PruebaDisposicionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("resultado", "Resultado"), ("separador", "Separador")], max_length=20)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("disposicion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="misc.pruebadisposicion")),
                ("resultado", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="items_disposicion", to="misc.pruebaresultado")),
                ("separador", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="items_disposicion", to="misc.pruebaseparador")),
            ],
            options={"ordering": ["orden", "id"]},
        ),
    ]
