from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('misc', '0019_prueba_catalog_units_tipo_gestion_suggestions'),
    ]

    operations = [
        migrations.CreateModel(
            name='LotePruebasPredefinido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('tipo_lote', models.CharField(choices=[('gestion', 'Por gestión'), ('uso', 'Por uso'), ('personalizado', 'Personalizado')], default='personalizado', max_length=20)),
                ('uso_referencia', models.CharField(blank=True, max_length=120, null=True)),
                ('es_default', models.BooleanField(default=False)),
                ('activo', models.BooleanField(default=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tipo_gestion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lotes_pruebas_predefinidos', to='misc.tipogestionmuestra')),
            ],
            options={
                'ordering': ['nombre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='LotePruebasPredefinidoDetalle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('condicion_texto', models.CharField(blank=True, max_length=120, null=True)),
                ('unidad', models.CharField(blank=True, max_length=40, null=True)),
                ('orden', models.PositiveIntegerField(default=1)),
                ('activo', models.BooleanField(default=True)),
                ('condicion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lotes_predefinidos_detalle', to='misc.condicion')),
                ('equipo_prueba', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lotes_predefinidos_detalle', to='misc.equipoprueba')),
                ('lote', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='misc.lotepruebaspredefinido')),
                ('metodo_equipo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lotes_predefinidos_detalle', to='misc.metodoequipo')),
                ('prueba', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lotes_predefinidos_detalle', to='misc.prueba')),
            ],
            options={
                'ordering': ['orden', 'id'],
                'unique_together': {('lote', 'prueba', 'orden')},
            },
        ),
        migrations.AddIndex(
            model_name='lotepruebaspredefinido',
            index=models.Index(fields=['tipo_lote'], name='misc_lotepr_tipo_lo_5fc275_idx'),
        ),
        migrations.AddIndex(
            model_name='lotepruebaspredefinido',
            index=models.Index(fields=['tipo_gestion'], name='misc_lotepr_tipo_ge_720e6d_idx'),
        ),
        migrations.AddIndex(
            model_name='lotepruebaspredefinido',
            index=models.Index(fields=['activo'], name='misc_lotepr_activo_47e17d_idx'),
        ),
    ]
