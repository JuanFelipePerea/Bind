"""
FIX DEFINITIVO para MultipleObjectsReturned en allauth 65.x

Raíz del problema:
    allauth 65.x → list_apps() COMBINA apps de settings + apps de DB.
    Con APP configurado en SOCIALACCOUNT_PROVIDERS *y* un registro en
    SocialApp (DB), list_apps() devuelve 2 apps → get_app() hace .get()
    → MultipleObjectsReturned en cada flujo OAuth.

Solución:
    Eliminar TODOS los registros SocialApp de Google de la BD.
    allauth usará exclusivamente la config de settings.SOCIALACCOUNT_PROVIDERS.
    SocialToken.app es nullable en allauth 65.x (migración 0005 de socialaccount),
    por lo que los tokens existentes no se ven afectados.

Referencias:
    allauth/socialaccount/adapter.py → list_apps() mezcla DB + settings
    allauth socialaccount migration 0005_socialtoken_nullable_app
"""
from django.db import migrations


def remove_google_db_apps(apps, schema_editor):
    """
    Borra todos los SocialApp de Google de la BD.
    Las credenciales viven en settings.SOCIALACCOUNT_PROVIDERS['google']['APP'].
    Los SocialToken existentes tienen app=NULL (nullable FK) y se conservan.
    """
    db = schema_editor.connection.alias
    SocialApp = apps.get_model('socialaccount', 'SocialApp')
    deleted, _ = SocialApp.objects.using(db).filter(provider='google').delete()
    # No hay nada más que hacer — settings-only config activa automáticamente.


def noop(apps, schema_editor):
    """Reverse no restaura los registros: la config de settings es suficiente."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_nuclear_socialapp_dedup'),
        ('socialaccount', '0005_socialtoken_nullable_app'),
    ]

    operations = [
        migrations.RunPython(remove_google_db_apps, noop),
    ]
