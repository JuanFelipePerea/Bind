"""
python manage.py setup_site

Inicializa el registro django.contrib.sites.Site con el dominio correcto
y crea el SocialApp de Google si no existe.

Ejecutar en Render Shell después de cada deploy inicial o migración.
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Configura Site domain y SocialApp de Google para allauth.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            default='',
            help='Dominio a usar (ej. bind-gexm.onrender.com). '
                 'Por defecto se lee de settings.SITE_URL.',
        )

    def handle(self, *args, **options):
        from django.contrib.sites.models import Site

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

        # ── 3. Verificar SocialApp de Google ─────────────────────────────────
        try:
            from allauth.socialaccount.models import SocialApp

            client_id = ''
            secret = ''

            providers_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
            google_cfg = providers_cfg.get('google', {})
            app_cfg = google_cfg.get('APP', {})
            client_id = app_cfg.get('client_id', '')
            secret = app_cfg.get('secret', '')

            if not client_id:
                self.stdout.write(self.style.WARNING(
                    'GOOGLE_CLIENT_ID no está configurado — SocialApp no creado. '
                    'Agrega GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET a las env vars de Render.'
                ))
                return

            app, app_created = SocialApp.objects.get_or_create(
                provider='google',
                defaults={
                    'name': 'Google OAuth',
                    'client_id': client_id,
                    'secret': secret,
                }
            )

            if not app_created:
                # Actualizar credenciales si cambiaron
                updated = False
                if app.client_id != client_id:
                    app.client_id = client_id
                    updated = True
                if app.secret != secret:
                    app.secret = secret
                    updated = True
                if updated:
                    app.save()
                    self.stdout.write(self.style.SUCCESS('SocialApp de Google actualizado.'))
                else:
                    self.stdout.write('SocialApp de Google ya estaba configurado correctamente.')
            else:
                self.stdout.write(self.style.SUCCESS('SocialApp de Google creado.'))

            # Vincular al Site si no lo está
            if site not in app.sites.all():
                app.sites.add(site)
                self.stdout.write(self.style.SUCCESS(
                    f'SocialApp vinculado a Site(domain={domain}).'
                ))

        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Error configurando SocialApp: {exc}'))
