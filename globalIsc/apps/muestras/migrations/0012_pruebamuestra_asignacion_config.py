from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('misc', '0020_lotepruebaspredefinido'),
        ('muestras', '0011_remove_muestra_muestras_mu_fabrica_394b9c_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pruebamuestra',
            name='condicion_configurada',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='equipo_configurado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pruebas_muestra_configuradas', to='misc.equipoprueba'),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='estado_asignacion',
            field=models.CharField(choices=[('borrador', 'Borrador'), ('confirmada', 'Confirmada')], default='confirmada', max_length=20),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='fecha_confirmacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='lote_predefinido',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pruebas_asignadas', to='misc.lotepruebaspredefinido'),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='metodo_configurado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pruebas_muestra_configuradas', to='misc.metodoequipo'),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='unidad_configurada',
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
    ]
