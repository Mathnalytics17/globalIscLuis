from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('activesTree', '0009_maquina_descripcion')]
    operations = [
        migrations.AddField(model_name='puntomuestreo', name='lubricante', field=models.CharField(blank=True, max_length=150, null=True)),
        migrations.AddField(model_name='puntomuestreo', name='frecuencia_cambio', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='puntomuestreo', name='unidad_frecuencia_cambio', field=models.CharField(default='horas', max_length=10)),
        migrations.AddField(model_name='puntomuestreo', name='frecuencia_analisis', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='puntomuestreo', name='unidad_frecuencia_analisis', field=models.CharField(default='horas', max_length=10)),
    ]
