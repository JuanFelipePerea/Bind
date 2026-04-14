"""
Prioritizer — ordena colecciones de eventos o tareas según criterios inteligentes.

A diferencia del simple orden por fecha, el Prioritizer combina:
- Urgencia temporal (días hasta el evento)
- Score de riesgo
- Progreso actual
- Prioridad de tareas pendientes

Usado por el dashboard para decidir qué mostrar primero.
"""


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
        # Alta puntuación = aparece primero; pocos días = más urgente
        return (-score, days)

    return sorted(events_with_scores, key=sort_key)


def prioritize_tasks(tasks):
    """
    Ordena un queryset de tareas según: prioridad → fecha límite → estado.
    Retorna lista de tareas ordenadas.
    """
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    status_order = {'pending': 0, 'in_progress': 1, 'done': 2}

    def task_sort_key(task):
        p = priority_order.get(task.priority, 99)
        s = status_order.get(task.status, 99)
        d = task.due_date.toordinal() if task.due_date else 999999
        return (s, p, d)

    return sorted(tasks, key=task_sort_key)
