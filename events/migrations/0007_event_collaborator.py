# Generated manually — EventCollaborator model
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_bynix_message_history'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EventCollaborator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('editor', 'Editor'), ('viewer', 'Visor')], default='viewer', max_length=10)),
                ('accepted', models.BooleanField(default=False)),
                ('invited_at', models.DateTimeField(auto_now_add=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaborators', to='events.event', verbose_name='Evento')),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_invitations', to=settings.AUTH_USER_MODEL, verbose_name='Invitado por')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_collaborations', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Colaborador de evento',
                'verbose_name_plural': 'Colaboradores de evento',
                'ordering': ['-invited_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='eventcollaborator',
            unique_together={('event', 'user')},
        ),
    ]
