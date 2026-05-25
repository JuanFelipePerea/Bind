"""
Migración nuclear: borra TODOS los SocialApp de Google y crea exactamente uno.

Reemplaza el enfoque de 0007 (que falló porque get_or_create lanzó
MultipleObjectsReturned cuando había más de 2 registros previos).
Esta migración no usa get_or_create — borra todo y crea desde cero.
"""
from django.db import migrations
from django.conf import settings


def nuclear_dedup(apps, schema_editor):
    db = schema_editor.connection.alias
    SocialApp = apps.get_model('socialaccount', 'SocialApp')
    Site = apps.get_model('sites', 'Site')

    # ── Borrar todos los SocialApp de Google existentes ───────────────────────
    SocialApp.objects.using(db).filter(provider='google').delete()

    # ── Leer credenciales desde env vars ──────────────────────────────────────
    providers_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    google_cfg = providers_cfg.get('google', {}).get('APP', {})
    client_id = google_cfg.get('client_id', '')
    secret = google_cfg.get('secret', '')

    if not client_id:
        # Sin credenciales (local sin .env) — no crear registro
        return

    # ── Crear uno solo, limpio ────────────────────────────────────────────────
    app = SocialApp.objects.using(db).create(
        provider='google',
        name='Google OAuth',
        client_id=client_id,
        secret=secret,
        key='',
    )

    # ── Vincular al Site correcto ─────────────────────────────────────────────
    SocialAppSites = app.sites.through
    try:
        site = Site.objects.using(db).get(id=settings.SITE_ID)
        SocialAppSites.objects.using(db).create(
            socialapp_id=app.pk,
            site_id=site.pk,
        )
    except Site.DoesNotExist:
        pass


def reverse_nuclear(apps, schema_editor):
    db = schema_editor.connection.alias
    apps.get_model('socialaccount', 'SocialApp').objects.using(db).filter(
        provider='google'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_deduplicate_socialapp_google'),
        ('socialaccount', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(nuclear_dedup, reverse_nuclear),
    ]
