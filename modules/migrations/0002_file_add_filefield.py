from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='file_path',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='file',
            name='file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='event_files/%Y/%m/',
                verbose_name='Archivo',
            ),
        ),
    ]
