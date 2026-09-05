import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('activesTree', '0006_remove_carpeta_activestree_parenti_04b3ec_idx_and_more'),
        ('muestras', '0023_historialmuestra'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PuntoMuestreo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('codigo', models.CharField(blank=True, max_length=80, null=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='puntos_muestreo_creados', to=settings.AUTH_USER_MODEL)),
                ('maquina', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='puntos_muestreo', to='activesTree.maquina')),
            ],
            options={'ordering': ['nombre', 'id']},
        ),
        migrations.CreateModel(
            name='AsignacionPuntoMuestreo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origen', models.CharField(choices=[('manual', 'Manual'), ('lote', 'Lote')], default='manual', max_length=20)),
                ('activa', models.BooleanField(db_index=True, default=True)),
                ('asignado_en', models.DateTimeField(auto_now_add=True)),
                ('finalizado_en', models.DateTimeField(blank=True, null=True)),
                ('asignado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asignaciones_punto_muestreo_realizadas', to=settings.AUTH_USER_MODEL)),
                ('muestra', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones_punto_muestreo', to='muestras.muestra')),
                ('punto_muestreo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='asignaciones', to='activesTree.puntomuestreo')),
            ],
            options={'ordering': ['-asignado_en', '-id']},
        ),
        migrations.AddConstraint(model_name='puntomuestreo', constraint=models.UniqueConstraint(condition=Q(activo=True), fields=('maquina', 'nombre'), name='unique_active_sampling_point_name_per_machine')),
        migrations.AddConstraint(model_name='asignacionpuntomuestreo', constraint=models.UniqueConstraint(condition=Q(activa=True), fields=('muestra',), name='one_active_sampling_point_per_sample')),
        migrations.AddIndex(model_name='puntomuestreo', index=models.Index(fields=['maquina', 'activo'], name='activesTree_maquina_e23418_idx')),
        migrations.AddIndex(model_name='asignacionpuntomuestreo', index=models.Index(fields=['punto_muestreo', 'activa'], name='activesTree_punto_m_ae84e0_idx')),
        migrations.AddIndex(model_name='asignacionpuntomuestreo', index=models.Index(fields=['muestra', 'activa'], name='activesTree_muestra_a1e9de_idx')),
    ]
