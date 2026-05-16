from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0007_event_collaborator'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='invitation_file',
            field=models.FileField(
                blank=True, null=True,
                upload_to='invitations/',
                verbose_name='Archivo de invitación',
                help_text='PDF o imagen adjunta al email de invitación.',
            ),
        ),
    ]
