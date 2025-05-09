# Generated by Django 5.1.6 on 2025-05-01 00:11

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('misc', '0001_initial'),
        ('muestras', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ingresolab',
            name='usuario_recepcion',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='muestra',
            name='lubricante',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='misc.lubricante'),
        ),
        migrations.AddField(
            model_name='muestra',
            name='referencia_equipo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='misc.referenciaequipo'),
        ),
        migrations.AddField(
            model_name='muestra',
            name='usuario_registro',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='ingresolab',
            name='muestra',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ingreso_lab', to='muestras.muestra'),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='muestra',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pruebas', to='muestras.muestra'),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='prueba',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='misc.prueba'),
        ),
        migrations.AddField(
            model_name='pruebamuestra',
            name='usuario_solicitud',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='pruebamuestra',
            unique_together={('muestra', 'prueba')},
        ),
    ]
