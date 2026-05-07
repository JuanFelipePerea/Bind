from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_add_momentos_to_module_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='layout_config',
            field=models.JSONField(blank=True, default=dict, verbose_name='Configuración de layout'),
        ),
    ]
