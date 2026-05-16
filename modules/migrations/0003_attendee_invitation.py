import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0002_fix_fk_cascade'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendee',
            name='invitation_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='attendee',
            name='invitation_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendee',
            name='token_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='AttendeePreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dietary', models.CharField(
                    choices=[
                        ('none', 'Sin restricciones'), ('vegetarian', 'Vegetariano'),
                        ('vegan', 'Vegano'), ('gluten_free', 'Sin gluten'),
                        ('halal', 'Halal'), ('kosher', 'Kosher'), ('other', 'Otro'),
                    ],
                    default='none', max_length=20, verbose_name='Restricción alimentaria',
                )),
                ('accessibility', models.BooleanField(default=False, verbose_name='Necesidades de accesibilidad')),
                ('notes', models.TextField(blank=True, verbose_name='Notas adicionales')),
                ('responded_at', models.DateTimeField(auto_now_add=True)),
                ('attendee', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preference',
                    to='modules.attendee',
                    verbose_name='Asistente',
                )),
            ],
            options={
                'verbose_name': 'Preferencia de asistente',
                'verbose_name_plural': 'Preferencias de asistentes',
            },
        ),
    ]
