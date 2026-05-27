"""
Management command: envía un resumen semanal personalizado a cada usuario activo.
Uso: python manage.py send_weekly_digest
     python manage.py send_weekly_digest --user john@example.com  (para pruebas)
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from events.email_utils import send_bind_email, SITE_URL
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía el resumen semanal de Bynix a todos los usuarios activos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Email del usuario específico (para pruebas)',
            default=None,
        )

    def handle(self, *args, **options):
        from events.stats import compute_user_stats
        from events.services.ai_service import generate_report_insights

        target_email = options.get('user')
        if target_email:
            users = User.objects.filter(email=target_email, is_active=True)
        else:
            users = User.objects.filter(is_active=True, email__isnull=False).exclude(email='')

        sent = 0
        failed = 0

        for user in users:
            try:
                self._send_digest(user, compute_user_stats, generate_report_insights)
                sent += 1
                self.stdout.write(f'  ✓ Enviado a {user.email}')
            except Exception as e:
                failed += 1
                logger.error(f'Error enviando digest a {user.email}: {e}')
                self.stdout.write(self.style.WARNING(f'  ✗ Error con {user.email}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nResumen semanal: {sent} enviados, {failed} fallidos.'
        ))

    def _send_digest(self, user, compute_user_stats, generate_report_insights):
        stats = compute_user_stats(user)

        # Si el usuario no tiene eventos activos, saltar
        if stats.get('total_events', 0) == 0:
            return

        try:
            insights = generate_report_insights(stats)
        except Exception:
            insights = {
                'resumen': 'Tu semana en BIND',
                'tendencia': 'estable',
                'score_salud': 50,
                'riesgos': [],
                'recomendaciones': [],
            }

        nombre = user.get_full_name() or user.username
        resumen = insights.get('resumen', 'Resumen de tu semana')
        score = insights.get('score_salud', 0)
        riesgos_raw = insights.get('riesgos', [])
        recomendaciones = insights.get('recomendaciones', [])[:3]
        tendencia = insights.get('tendencia', 'estable')

        # Normalizar riesgos a lista de dicts
        riesgos = []
        for r in riesgos_raw[:3]:
            if isinstance(r, dict):
                riesgos.append(r)
            else:
                riesgos.append({'nivel': '', 'descripcion': str(r)})

        # Cargar plantilla personalizada del usuario (si existe)
        from accounts.models import EmailTemplate
        digest_tpl = EmailTemplate.objects.filter(user=user, email_type='digest').first()

        if digest_tpl and digest_tpl.custom_subject:
            subject = digest_tpl.get_subject()
        else:
            subject = f"Bynix · Tu semana: {resumen[:60]}"

        custom_message = digest_tpl.get_body() if digest_tpl else ''

        send_bind_email(
            template_name='resumen_semanal',
            subject=subject,
            recipient=user.email,
            context={
                'nombre': nombre,
                'resumen': resumen,
                'score': score,
                'tendencia': tendencia,
                'active_events': stats.get('active_events', 0),
                'pending_tasks': stats.get('pending_tasks', 0),
                'riesgos': riesgos,
                'recomendaciones': recomendaciones,
                'site_url': SITE_URL,
                'custom_message': custom_message,
            },
        )
