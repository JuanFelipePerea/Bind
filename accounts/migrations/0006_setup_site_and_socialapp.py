"""
Migración de datos: configura Site domain y SocialApp de Google automáticamente.

Lee SITE_URL y GOOGLE_CLIENT_ID/SECRET desde variables de entorno,
por lo que funciona en cualquier entorno (Render, local, staging) sin
necesidad de acceso a shell ni intervención manual.

Se ejecuta en cada `python manage.py migrate`, pero es idempotente:
actualiza si existe, crea si no existe.
"""
from django.db import migrations
from django.conf import settings


def setup_site_and_socialapp(apps, schema_editor):
    db = schema_editor.connection.alias

    Site = apps.get_model('sites', 'Site')
    SocialApp = apps.get_model('socialaccount', 'SocialApp')

    # ── 1. Resolver dominio desde SITE_URL ────────────────────────────────────
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        domain = site_url.replace('https://', '').replace('http://', '')
        name = 'BIND'
    else:
        # En local sin SITE_URL, dejar el valor que ya exista o usar localhost
        try:
            existing = Site.objects.using(db).get(id=settings.SITE_ID)
            # No pisar un dominio ya configurado correctamente
            if existing.domain not in ('example.com', 'example.org', ''):
                domain = existing.domain
                name = existing.name
            else:
                domain = '127.0.0.1:8000'
                name = 'BIND (local)'
        except Site.DoesNotExist:
            domain = '127.0.0.1:8000'
            name = 'BIND (local)'

    # ── 2. Actualizar / crear Site ────────────────────────────────────────────
    Site.objects.using(db).update_or_create(
        id=settings.SITE_ID,
        defaults={'domain': domain, 'name': name},
    )

    # ── 3. Credenciales de Google desde env ───────────────────────────────────
    providers_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    google_cfg = providers_cfg.get('google', {})
    app_cfg = google_cfg.get('APP', {})
    client_id = app_cfg.get('client_id', '')
    secret = app_cfg.get('secret', '')

    # Sin credenciales no creamos SocialApp (local sin .env, por ejemplo)
    if not client_id:
        return

    # ── 4. Crear o actualizar SocialApp de Google ─────────────────────────────
    app, created = SocialApp.objects.using(db).get_or_create(
        provider='google',
        defaults={
            'name': 'Google OAuth',
            'client_id': client_id,
            'secret': secret,
            'key': '',
        },
    )

    if not created:
        changed = False
        if app.client_id != client_id:
            app.client_id = client_id
            changed = True
        if app.secret != secret:
            app.secret = secret
            changed = True
        if changed:
            app.save(using=db)

    # ── 5. Vincular SocialApp al Site ─────────────────────────────────────────
    site = Site.objects.using(db).get(id=settings.SITE_ID)
    # ManyToMany — usar through table directamente para evitar problemas con
    # apps proxy en migraciones
    SocialAppSites = app.sites.through
    if not SocialAppSites.objects.using(db).filter(
        socialapp_id=app.pk,
        site_id=site.pk,
    ).exists():
        SocialAppSites.objects.using(db).create(
            socialapp_id=app.pk,
            site_id=site.pk,
        )


def reverse_setup(apps, schema_editor):
    # Revertir: restaurar Site a example.com y eliminar el SocialApp de Google
    db = schema_editor.connection.alias
    Site = apps.get_model('sites', 'Site')
    SocialApp = apps.get_model('socialaccount', 'SocialApp')

    Site.objects.using(db).filter(id=settings.SITE_ID).update(
        domain='example.com', name='example.com'
    )
    SocialApp.objects.using(db).filter(provider='google').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_add_two_factor_sent_at'),
        ('sites', '0002_alter_domain_unique'),
        ('socialaccount', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(setup_site_and_socialapp, reverse_setup),
    ]
