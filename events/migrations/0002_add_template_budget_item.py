from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        # ── Nuevos MODULE_CHOICES con 'budget' ────────────────────────────────
        migrations.AlterField(
            model_name='templatemodule',
            name='module_type',
            field=models.CharField(
                choices=[
                    ('tasks', 'Tareas'),
                    ('attendees', 'Asistentes'),
                    ('checklist', 'Checklist'),
                    ('files', 'Archivos'),
                    ('budget', 'Presupuesto'),
                ],
                max_length=20,
                verbose_name='Módulo',
            ),
        ),
        migrations.AlterField(
            model_name='eventmodule',
            name='module_type',
            field=models.CharField(
                choices=[
                    ('tasks', 'Tareas'),
                    ('attendees', 'Asistentes'),
                    ('checklist', 'Checklist'),
                    ('files', 'Archivos'),
                    ('budget', 'Presupuesto'),
                ],
                max_length=20,
                verbose_name='Módulo',
            ),
        ),
        migrations.AlterField(
            model_name='eventmodule',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Activo'),
        ),

        # ── Nuevo modelo: TemplateBudgetItem ──────────────────────────────────
        migrations.CreateModel(
            name='TemplateBudgetItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    help_text='Descripción del gasto o ingreso estimado.',
                    max_length=200,
                    verbose_name='Concepto',
                )),
                ('amount_estimate', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Valor de referencia. Puede ajustarse al crear el evento.',
                    max_digits=12,
                    verbose_name='Monto estimado',
                )),
                ('item_type', models.CharField(
                    choices=[('expense', 'Gasto'), ('income', 'Ingreso')],
                    default='expense',
                    max_length=10,
                    verbose_name='Tipo',
                )),
                ('category', models.CharField(
                    choices=[
                        ('venue', 'Lugar/Espacio'),
                        ('catering', 'Catering'),
                        ('marketing', 'Marketing'),
                        ('technology', 'Tecnología'),
                        ('staff', 'Personal'),
                        ('transport', 'Transporte'),
                        ('other', 'Otro'),
                    ],
                    default='other',
                    max_length=20,
                    verbose_name='Categoría',
                )),
                ('order', models.IntegerField(default=0, verbose_name='Orden')),
                ('template', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='default_budget_items',
                    to='events.eventtemplate',
                )),
            ],
            options={
                'verbose_name': 'Ítem de presupuesto de plantilla',
                'verbose_name_plural': 'Ítems de presupuesto de plantilla',
                'ordering': ['order'],
            },
        ),
    ]
