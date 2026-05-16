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
        critical = [d for d in decisions if d.severity == 'critical']
        warnings  = [d for d in decisions if d.severity == 'warning']

        subject_prefix = 'Accion urgente' if critical else 'Atencion requerida'
        subject = f'{subject_prefix} en BIND — {nombre}'

        lines = [
            f'Hola {nombre},',
            '',
            'Bynix detectó situaciones que requieren tu atención:',
            '',
        ]

        if critical:
            lines.append('CRITICO — actua hoy:')
            for d in critical:
                lines.append(f'  · {d.title}')
                lines.append(f'    {d.message}')
                if d.action_url:
                    lines.append(f'    -> {SITE_URL}{d.action_url}')
                lines.append('')

        if warnings:
            lines.append('Advertencias:')
            for d in warnings:
                lines.append(f'  · {d.title}')
                lines.append(f'    {d.message}')
                lines.append('')

        lines += [
            f'Ver tu panel: {SITE_URL}/dashboard/',
            '',
            '— Bynix, asistente de BIND',
        ]

        send_mail(
            subject=subject,
            message='\n'.join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
