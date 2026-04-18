from django.db import migrations


def configure_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    Site.objects.update_or_create(
        id=1,
        defaults={'domain': 'localhost:8000', 'name': 'BIND'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_userprofile_avatar'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(configure_site, migrations.RunPython.noop),
    ]
