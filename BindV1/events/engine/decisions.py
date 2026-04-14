"""
Decisions — traduce scores y contextos en decisiones concretas.

Una Decision es una recomendación accionable: no solo "hay un problema"
sino "esto es lo que debes hacer ahora". Las decisions alimentan tanto
las alertas (EventAlert) como el panel de sugerencias del dashboard.
"""

from dataclasses import dataclass, field
from typing import Optional


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


def derive_decisions(ctx, score: int) -> list:
    """
    Dado un EventContext y su score, retorna una lista de Decision.
    Cada decision representa una recomendación accionable.
    """
    decisions = []

    if ctx.days_until is not None and ctx.days_until <= 3 and ctx.task_high_pending > 0:
        decisions.append(Decision(
            title="Evento inminente con tareas críticas sin completar",
            message=f"Quedan {ctx.task_high_pending} tarea(s) de alta prioridad. El evento es en {ctx.days_until} día(s).",
            action_url=f"/modules/events/{ctx.event.pk}/tasks/",
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
            action_url=f"/modules/events/{ctx.event.pk}/tasks/",
            action_label="Ver tareas",
            severity='critical',
            alert_type='deadline',
            alert_key=f"critical-low-progress-{ctx.event.pk}",
        ))

    return decisions
