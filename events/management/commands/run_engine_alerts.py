"""
Management command: corre el Decision Engine para todos los usuarios activos
y envía emails de alerta para decisiones críticas o de advertencia.

Uso:
    python manage.py run_engine_alerts                          # todos los usuarios
    python manage.py run_engine_alerts --user john@example.com  # usuario específico (prueba)
    python manage.py run_engine_alerts --dry-run                # simula sin enviar emails
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from events.email_utils import send_bind_email
import logging

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://bind.onrender.com')


class Command(BaseCommand):
    help = 'Ejecuta el Decision Engine y envía alertas críticas por email'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, default=None,
                            help='Email del usuario específico para pruebas')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Simula la ejecución sin enviar emails ni persistir alertas')
        parser.add_argument('--min-severity', type=str, default='warning',
                            choices=['critical', 'warning', 'info'],
                            help='Severidad mínima para enviar email (default: warning)')

    def handle(self, *args, **options):
        from events.engine import run_engine_for_user

        dry_run = options['dry_run']
        min_sev = options['min_severity']
        target_email = options.get('user')

        sev_order = {'critical': 0, 'warning': 1, 'info': 2}
        min_sev_level = sev_order[min_sev]

        if target_email:
            users = User.objects.filter(email=target_email, is_active=True)
        else:
            users = User.objects.filter(
                is_active=True, email__isnull=False
            ).exclude(email='')

        total_emails = 0
        total_errors = 0

        for user in users:
            try:
                output = run_engine_for_user(user)
                decisions = output.get('all_decisions', [])

                # Filtrar por severidad mínima
                relevant = [
                    d for d in decisions
                    if sev_order.get(d.severity, 99) <= min_sev_level
                ]

                if not relevant:
                    self.stdout.write(f'  - {user.email}: sin alertas relevantes')
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  [DRY RUN] {user.email}: {len(relevant)} alerta(s) -- no se envia email'
                        )
                    )
                    for d in relevant:
                        self.stdout.write(f'    [{d.severity.upper()}] {d.title}')
                    continue

                self._send_alert_email(user, relevant)
                total_emails += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  OK {user.email}: {len(relevant)} alerta(s) enviadas'
                ))

            except Exception as e:
                total_errors += 1
                logger.error(f'Error procesando alertas para {user.email}: {e}')
                self.stdout.write(self.style.WARNING(f'  ERROR {user.email}: {e}'))

        mode = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{mode}Engine alerts: {total_emails} emails enviados, {total_errors} errores.'
        ))

    def _send_alert_email(self, user, decisions):
        nombre = user.get_full_name() or user.username
        criticos    = [d for d in decisions if d.severity == 'critical']
        advertencias = [d for d in decisions if d.severity == 'warning']

        # Cargar plantilla personalizada del usuario (si existe)
        from accounts.models import EmailTemplate
        alert_tpl = EmailTemplate.objects.filter(user=user, email_type='alert').first()

        if alert_tpl and alert_tpl.custom_subject:
            subject = alert_tpl.get_subject()
        else:
            subject_prefix = '🚨 Acción urgente' if criticos else '⚠️ Atención requerida'
            subject = f'{subject_prefix} en BIND — {nombre}'

        custom_message = alert_tpl.get_body() if alert_tpl else ''

        send_bind_email(
            template_name='alertas_engine',
            subject=subject,
            recipient=user.email,
            context={
                'nombre': nombre,
                'hay_criticos': bool(criticos),
                'criticos': criticos,
                'advertencias': advertencias,
                'site_url': SITE_URL,
                'custom_message': custom_message,
            },
        )
