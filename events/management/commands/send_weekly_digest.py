"""
Management command: envía un resumen semanal personalizado a cada usuario activo.
Uso: python manage.py send_weekly_digest
     python manage.py send_weekly_digest --user john@example.com  (para pruebas)
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
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
        # riesgos es una lista de dicts: {"nivel": "...", "descripcion": "..."}
        riesgos_raw = insights.get('riesgos', [])
        recomendaciones = insights.get('recomendaciones', [])
        tendencia = insights.get('tendencia', 'estable')

        # Construir cuerpo del email
        lines = [
            f"Hola {nombre},",
            "",
            "Bynix tiene tu resumen de la semana:",
            "",
            f"📊 {resumen}",
            f"Salud general: {score}/100  |  Tendencia: {tendencia}",
            "",
        ]

        active = stats.get('active_events', 0)
        pending = stats.get('pending_tasks', 0)
        lines.append(f"Tienes {active} evento(s) activo(s) y {pending} tarea(s) pendiente(s).")
        lines.append("")

        if riesgos_raw:
            lines.append("⚠️ Puntos de atención:")
            for r in riesgos_raw[:3]:
                # Cada riesgo es un dict con claves "nivel" y "descripcion"
                if isinstance(r, dict):
                    descripcion = r.get('descripcion', str(r))
                    nivel = r.get('nivel', '')
                    prefix = f"[{nivel.upper()}] " if nivel else ""
                    lines.append(f"  · {prefix}{descripcion}")
                else:
                    lines.append(f"  · {r}")
            lines.append("")

        if recomendaciones:
            lines.append("✅ Recomendaciones de Bynix:")
            for rec in recomendaciones[:3]:
                lines.append(f"  · {rec}")
            lines.append("")

        lines += [
            "— Bynix, tu asistente BIND",
            "",
            f"Ver tu dashboard: {getattr(settings, 'SITE_URL', 'https://bind.onrender.com')}/dashboard/",
        ]

        body = "\n".join(lines)
        subject = f"Bynix · Tu semana: {resumen[:60]}"

        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
