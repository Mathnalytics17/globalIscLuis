from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0028_lotepruebaspredefinidodetalle_criterio_limite_valor"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampoTecnicoMuestra",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activo", models.BooleanField(default=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nombre_visible", models.CharField(max_length=140)),
                ("codigo", models.SlugField(max_length=100)),
                ("tipo_muestra", models.CharField(choices=[("aceite", "Aceite"), ("grasa", "Grasa"), ("ambos", "Ambos")], default="ambos", max_length=20)),
                ("obligatorio", models.BooleanField(default=False)),
                ("permite_desconocido", models.BooleanField(default=True)),
                ("visible_en_ingreso", models.BooleanField(default=True)),
                ("visible_en_asignacion", models.BooleanField(default=True)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("ayuda", models.CharField(blank=True, max_length=255, null=True)),
                ("catalogo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="campos_muestra", to="misc.catalogotecnico")),
            ],
            options={
                "ordering": ["tipo_muestra", "orden", "nombre_visible"],
                "unique_together": {("tipo_muestra", "codigo")},
            },
        ),
        migrations.AlterField(
            model_name="pruebafuentelimite",
            name="tipo_limite",
            field=models.CharField(choices=[("catalogo", "Catalogo tecnico"), ("campo_muestra", "Campo tecnico de muestra"), ("seleccion_asignacion", "Seleccion al asignar"), ("global", "Global"), ("sin_limite", "Sin limite")], default="catalogo", max_length=30),
        ),
        migrations.AddField(
            model_name="pruebafuentelimite",
            name="campo_tecnico_muestra",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fuentes_limite", to="misc.campotecnicomuestra"),
        ),
        migrations.CreateModel(
            name="CriterioEvaluacionLimite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activo", models.BooleanField(default=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nombre", models.CharField(max_length=160)),
                ("codigo", models.SlugField(max_length=140)),
                ("tipo_criterio", models.CharField(choices=[("catalogo_item", "Item de catalogo"), ("escala_item", "Item de escala"), ("valor_fijo", "Valor fijo"), ("booleano", "Booleano"), ("opcion", "Opcion")], default="catalogo_item", max_length=30)),
                ("valor", models.CharField(blank=True, max_length=120, null=True)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("orden", models.PositiveIntegerField(default=1)),
                ("catalogo_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="criterios_limite", to="misc.catalogotecnicoitem")),
                ("escala_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="criterios_limite", to="misc.escalacomparacionitem")),
                ("fuente_limite", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="criterios", to="misc.pruebafuentelimite")),
            ],
            options={
                "ordering": ["fuente_limite", "orden", "nombre"],
                "unique_together": {("fuente_limite", "codigo")},
            },
        ),
    ]
