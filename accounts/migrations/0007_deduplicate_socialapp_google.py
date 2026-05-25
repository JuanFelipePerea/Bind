"""
Migración de datos: elimina SocialApp duplicados de Google.

La migración 0006 puede haber creado un segundo registro si ya existía uno
previo en la base de datos (ej. creado desde el admin de Django). Allauth
65.x llama a SocialApp.objects.get(provider='google') internamente, lo que
lanza MultipleObjectsReturned cuando hay más de uno.

Esta migración:
1. Detecta duplicados de provider='google'
2. Conserva el que tenga client_id real (o el más reciente)
3. Migra los sites al sobreviviente
4. Elimina los duplicados
5. Actualiza credenciales desde env vars
"""
from django.db import migrations
from django.conf import settings


def deduplicate_google_socialapp(apps, schema_editor):
    db = schema_editor.connection.alias
    SocialApp = apps.get_model('socialaccount', 'SocialApp')
    Site = apps.get_model('sites', 'Site')

    google_apps = list(SocialApp.objects.using(db).filter(provider='google').order_by('id'))

    if len(google_apps) <= 1:
        # Sin duplicados — solo actualizar credenciales si es necesario
        if google_apps:
            _sync_credentials(google_apps[0], apps, db)
        return

    # ── Elegir el sobreviviente: el que tenga client_id real, si no el primero
    providers_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    env_client_id = providers_cfg.get('google', {}).get('APP', {}).get('client_id', '')

    survivor = next(
        (a for a in google_apps if a.client_id == env_client_id and env_client_id),
        None
    ) or next(
        (a for a in google_apps if a.client_id and a.client_id != ''),
        None
    ) or google_apps[0]

    duplicates = [a for a in google_apps if a.pk != survivor.pk]

    # Reunir todos los sites de los duplicados en el sobreviviente
    SocialAppSites = survivor.sites.through
    survivor_site_ids = set(
        SocialAppSites.objects.using(db)
        .filter(socialapp_id=survivor.pk)
        .values_list('site_id', flat=True)
    )

    for dup in duplicates:
        dup_site_ids = set(
            SocialAppSites.objects.using(db)
            .filter(socialapp_id=dup.pk)
            .values_list('site_id', flat=True)
        )
        for site_id in dup_site_ids - survivor_site_ids:
            SocialAppSites.objects.using(db).create(
                socialapp_id=survivor.pk,
                site_id=site_id,
            )
            survivor_site_ids.add(site_id)

        # Eliminar el duplicado (cascade elimina sus SocialAppSites)
        SocialApp.objects.using(db).filter(pk=dup.pk).delete()

    # Sincronizar credenciales del sobreviviente con env vars
    _sync_credentials(survivor, apps, db)

    # Asegurar que el Site correcto esté vinculado
    try:
        site = Site.objects.using(db).get(id=settings.SITE_ID)
        if not SocialAppSites.objects.using(db).filter(
            socialapp_id=survivor.pk, site_id=site.pk
        ).exists():
            SocialAppSites.objects.using(db).create(
                socialapp_id=survivor.pk, site_id=site.pk
            )
    except Site.DoesNotExist:
        pass


def _sync_credentials(app, apps, db):
    """Actualiza client_id/secret del SocialApp con los valores de env vars."""
    providers_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    google_cfg = providers_cfg.get('google', {}).get('APP', {})
    client_id = google_cfg.get('client_id', '')
    secret = google_cfg.get('secret', '')

    if not client_id:
        return

    changed = False
    if app.client_id != client_id:
        app.client_id = client_id
        changed = True
    if app.secret != secret:
        app.secret = secret
        changed = True
    if changed:
        app.save(using=db)


def reverse_dedup(apps, schema_editor):
    pass  # No reversible de forma significativa


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_setup_site_and_socialapp'),
        ('socialaccount', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(deduplicate_google_socialapp, reverse_dedup),
    ]
