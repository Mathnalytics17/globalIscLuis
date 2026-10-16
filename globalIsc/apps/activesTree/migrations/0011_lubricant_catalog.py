from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('activesTree', '0010_sampling_point_lubrication_config')]

    operations = [
        migrations.CreateModel(
            name='Lubricante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('fabricante', models.CharField(blank=True, default='', max_length=150)),
                ('referencia', models.CharField(blank=True, default='', max_length=150)),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lubricantes', to='misc.empresa')),
            ],
            options={'ordering': ['nombre', 'id']},
        ),
        migrations.AddConstraint(
            model_name='lubricante',
            constraint=models.UniqueConstraint(fields=('empresa', 'nombre', 'fabricante', 'referencia'), name='unique_lubricant_per_company_identity'),
        ),
        migrations.AddField(
            model_name='puntomuestreo', name='lubricante_catalogo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='puntos_muestreo', to='activesTree.lubricante'),
        ),
    ]
