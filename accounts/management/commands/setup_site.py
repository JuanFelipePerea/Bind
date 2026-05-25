"""
python manage.py setup_site

Actualiza el registro django.contrib.sites.Site con el dominio correcto.

NOTA: En allauth 65.x, list_apps() combina registros de DB + settings.
Con APP configurado en SOCIALACCOUNT_PROVIDERS, NO debe haber SocialApp
en la base de datos — de lo contrario get_app() recibe 2 apps y lanza
MultipleObjectsReturned. Las credenciales viven en settings (env vars).

Este comando solo gestiona Site, no SocialApp.
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Configura Site domain para django.contrib.sites (allauth).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            default='',
            help='Dominio a usar (ej. bind-gexm.onrender.com). '
                 'Por defecto se lee de settings.SITE_URL.',
        )

    def handle(self, *args, **options):
        from django.contrib.sites.models import Site
        from allauth.socialaccount.models import SocialApp

        # ── 1. Resolver dominio ───────────────────────────────────────────────
        domain = options['domain']
        if not domain:
            site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
            if site_url:
                domain = site_url.replace('https://', '').replace('http://', '')

        if not domain:
            self.stderr.write(self.style.ERROR(
                'No se pudo determinar el dominio. '
                'Usa --domain o configura SITE_URL en las variables de entorno.'
            ))
            return

        # ── 2. Actualizar Site ────────────────────────────────────────────────
        site, created = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={'domain': domain, 'name': 'BIND'},
        )
        verb = 'Creado' if created else 'Actualizado'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} Site(id={settings.SITE_ID}, domain={domain})'
        ))

        # ── 3. Sanity check: no debe haber SocialApp de Google en DB ─────────
        google_apps = SocialApp.objects.filter(provider='google')
        count = google_apps.count()
        if count > 0:
            self.stdout.write(self.style.WARNING(
                f'ADVERTENCIA: {count} SocialApp(s) de Google en DB. '
                'Con APP en SOCIALACCOUNT_PROVIDERS esto causa MultipleObjectsReturned. '
                'Ejecutando limpieza...'
            ))
            google_apps.delete()
            self.stdout.write(self.style.SUCCESS(
                'SocialApps de Google eliminados. allauth usará SOCIALACCOUNT_PROVIDERS.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'OK: 0 SocialApps de Google en DB (allauth usa settings).'
            ))
