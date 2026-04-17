"""
Prioritizer — ordena colecciones de eventos o tareas según criterios inteligentes.

A diferencia del simple orden por fecha, el Prioritizer combina:
- Urgencia temporal (días hasta el evento)
- Score de riesgo
- Progreso actual
- Prioridad de tareas pendientes

Usado por el dashboard para decidir qué mostrar primero.
"""

from types import SimpleNamespace
from django.utils import timezone


def prioritize_events(events_with_scores: list) -> list:
    """
    Ordena una lista de dicts {event, score, context, decisions}
    según criterio compuesto de urgencia + riesgo.

    Retorna la lista ordenada (más urgente primero).
    """
    def sort_key(item):
        score = item.get('score', 0)
        ctx = item.get('context')
        days = ctx.days_until if ctx and ctx.days_until is not None else 999
        # Extraer valor numérico si score es un EventScore
        score_val = score.risk_level if hasattr(score, 'risk_level') else score
        # Alta puntuación = aparece primero; pocos días = más urgente
        return (-score_val, days)

    return sorted(events_with_scores, key=sort_key)


def prioritize_tasks(tasks):
    """
    Ordena un queryset/lista de tareas según: prioridad → fecha límite → estado.

    Retorna lista de SimpleNamespace con:
      .task          — objeto Task original
      .reason        — texto explicativo de por qué está en esa posición
      .urgency_score — valor numérico de urgencia (mayor = más urgente)
    """
    from django.utils import timezone as tz

    today = tz.now().date()

    priority_weight = {'high': 30, 'medium': 15, 'low': 5}
    status_weight = {'pending': 10, 'in_progress': 8, 'done': 0}

    def _build_reason(task) -> str:
        parts = []
        priority_label = {'high': 'Alta prioridad', 'medium': 'Prioridad media', 'low': 'Baja prioridad'}
        parts.append(priority_label.get(task.priority, 'Sin prioridad'))

        if task.due_date:
            delta = (task.due_date - today).days
            if delta < 0:
                parts.append(f'Vencida hace {abs(delta)} día{"s" if abs(delta) != 1 else ""}')
            elif delta == 0:
                parts.append('Vence hoy')
            elif delta == 1:
                parts.append('Vence mañana')
            elif delta <= 7:
                parts.append(f'Vence en {delta} días')
        else:
            parts.append('Sin fecha límite')

        if task.status == 'in_progress':
            parts.append('En progreso')

        return ' · '.join(parts)

    def _urgency_score(task) -> int:
        score = priority_weight.get(task.priority, 0)
        score += status_weight.get(task.status, 0)
        if task.due_date:
            delta = (task.due_date - today).days
            if delta < 0:
                score += 40  # vencida
            elif delta == 0:
                score += 30  # hoy
            elif delta <= 3:
                score += 20
            elif delta <= 7:
                score += 10
        return score

    result = []
    for task in tasks:
        result.append(SimpleNamespace(
            task=task,
            reason=_build_reason(task),
            urgency_score=_urgency_score(task),
        ))

    result.sort(key=lambda s: -s.urgency_score)
    return result
