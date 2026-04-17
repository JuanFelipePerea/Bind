"""
Decisions — traduce scores y contextos en decisiones concretas.

Una Decision es una recomendación accionable: no solo "hay un problema"
sino "esto es lo que debes hacer ahora". Las decisions alimentan tanto
las alertas (EventAlert) como el panel de sugerencias del dashboard.

Reglas implementadas:
  CRITICAL:
    - Evento inminente (<=3 días) con tareas de alta prioridad pendientes
    - Evento activo (<=7 días) con menos del 50% de tareas completadas
  WARNING:
    - Sin actividad 7+ días, evento en <=30 días       → stalled-{pk}-w{week}
    - 3+ tareas vencidas                               → overdue-tasks-{pk}
    - Asistentes pendientes, evento en <=7 días        → pending-attendees-{pk}
  INFO:
    - Sin fecha, más de 5 tareas                       → no-date-{pk}
    - Evento activo sin tareas                         → no-tasks-{pk}
"""

from dataclasses import dataclass, field
from typing import Optional
from django.urls import reverse


@dataclass
class Decision:
    """Recomendación concreta generada por el engine."""
    title: str
    message: str
    action_url: str = ''
    action_label: str = 'Ver ahora'
    severity: str = 'info'   # info | warning | critical
    alert_type: str = 'suggestion'
    alert_key: str = ''


def derive_decisions(ctx, score) -> list:
    """
    Dado un EventContext y su score, retorna una lista de Decision.
    Cada decision representa una recomendación accionable.
    """
    from django.utils import timezone
    decisions = []
    today = timezone.now().date()
    week_number = today.isocalendar()[1]

    # ── CRITICAL ─────────────────────────────────────────────────────────────

    if ctx.days_until is not None and ctx.days_until <= 3 and ctx.task_high_pending > 0:
        decisions.append(Decision(
            title="Evento inminente con tareas críticas sin completar",
            message=f"Quedan {ctx.task_high_pending} tarea(s) de alta prioridad. El evento es en {ctx.days_until} día(s).",
            action_url=reverse('modules:task_list', kwargs={'event_pk': ctx.event.pk}),
            action_label="Ver tareas",
            severity='critical',
            alert_type='deadline',
            alert_key=f"critical-imminent-hp-{ctx.event.pk}",
        ))

    if (ctx.days_until is not None and ctx.days_until <= 7
            and ctx.task_total > 0
            and ctx.progress_pct < 50):
        decisions.append(Decision(
            title="El progreso es insuficiente para la fecha del evento",
            message=f"Solo el {ctx.progress_pct}% completado con {ctx.days_until} día(s) restantes.",
            action_url=reverse('modules:task_list', kwargs={'event_pk': ctx.event.pk}),
            action_label="Ver tareas",
            severity='critical',
            alert_type='deadline',
            alert_key=f"critical-low-progress-{ctx.event.pk}",
        ))

    # ── WARNING ──────────────────────────────────────────────────────────────

    # Sin actividad 7+ días, evento en <=30 días
    if (ctx.last_activity_days is not None
            and ctx.last_activity_days >= 7
            and ctx.days_until is not None
            and 0 <= ctx.days_until <= 30):
        decisions.append(Decision(
            title="Este evento lleva más de 7 días sin actividad",
            message=(
                f"Sin actividad hace {ctx.last_activity_days} día(s). "
                f"Faltan {ctx.days_until} día(s) para el evento."
            ),
            action_url=reverse('modules:task_list', kwargs={'event_pk': ctx.event.pk}),
            action_label="Retomar",
            severity='warning',
            alert_type='stalled',
            alert_key=f"stalled-{ctx.event.pk}-w{week_number}",
        ))

    # 3+ tareas vencidas
    if ctx.task_overdue >= 3:
        decisions.append(Decision(
            title=f"Tienes {ctx.task_overdue} tareas vencidas en este evento",
            message=(
                f"{ctx.task_overdue} tarea(s) tienen fecha límite vencida "
                f"y aún no se han completado."
            ),
            action_url=reverse('modules:task_list', kwargs={'event_pk': ctx.event.pk}),
            action_label="Revisar tareas",
            severity='warning',
            alert_type='deadline',
            alert_key=f"overdue-tasks-{ctx.event.pk}",
        ))

    # Asistentes pendientes, evento en <=7 días
    if (ctx.days_until is not None
            and 0 <= ctx.days_until <= 7
            and ctx.attendee_pending > 0):
        decisions.append(Decision(
            title=f"{ctx.attendee_pending} asistente(s) no han confirmado su asistencia",
            message=(
                f"El evento es en {ctx.days_until} día(s) "
                f"y {ctx.attendee_pending} persona(s) aún están como pendientes."
            ),
            action_url=reverse('modules:attendee_list', kwargs={'event_pk': ctx.event.pk}),
            action_label="Ver asistentes",
            severity='warning',
            alert_type='attendance',
            alert_key=f"pending-attendees-{ctx.event.pk}",
        ))

    # ── INFO ─────────────────────────────────────────────────────────────────

    # Sin fecha de inicio y con más de 5 tareas
    if not ctx.has_start_date and ctx.task_total > 5:
        decisions.append(Decision(
            title="Este evento no tiene fecha definida",
            message=(
                f"El evento tiene {ctx.task_total} tareas pero sin fecha de inicio. "
                f"Definir una fecha ayudará a calcular plazos automáticamente."
            ),
            action_url=reverse('events:event_edit', kwargs={'pk': ctx.event.pk}),
            action_label="Definir fecha",
            severity='info',
            alert_type='suggestion',
            alert_key=f"no-date-{ctx.event.pk}",
        ))

    # Evento activo sin tareas
    if ctx.event.status == 'active' and ctx.task_total == 0:
        decisions.append(Decision(
            title="Este evento no tiene tareas asignadas",
            message=(
                f"El evento está activo pero sin tareas. "
                f"Agrega tareas para hacer seguimiento del progreso."
            ),
            action_url=reverse('modules:task_create', kwargs={'event_pk': ctx.event.pk}),
            action_label="Agregar tarea",
            severity='info',
            alert_type='suggestion',
            alert_key=f"no-tasks-{ctx.event.pk}",
        ))

    return decisions
