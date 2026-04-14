"""
Context Builder — reúne toda la información relevante de un evento
en una estructura unificada que el resto del engine puede consumir.

Responsabilidad: dado un Event, construir un EventContext con:
- Días restantes hasta el evento
- Progreso de tareas (total, completadas, vencidas)
- Estado de asistentes
- Última actividad
- Señales de riesgo crudas (sin interpretar aún)
"""


class EventContext:
    """
    Snapshot del estado de un evento en un momento dado.
    Construido por build_event_context() y consumido por scorer, decisions, etc.
    """

    def __init__(self, event):
        self.event = event
        self.days_until = None
        self.task_total = 0
        self.task_done = 0
        self.task_pending = 0
        self.task_overdue = 0
        self.task_high_pending = 0
        self.attendee_total = 0
        self.attendee_pending = 0
        self.last_activity_days = None
        self.has_start_date = False
        self.progress_pct = 0


def build_event_context(event):
    """
    Construye y retorna un EventContext para el evento dado.
    Centraliza todos los cálculos de estado del evento.
    """
    from django.utils import timezone

    ctx = EventContext(event)
    today = timezone.now().date()

    ctx.has_start_date = event.start_date is not None
    if ctx.has_start_date:
        ctx.days_until = (event.start_date.date() - today).days

    tasks = event.tasks.all()
    ctx.task_total = tasks.count()
    ctx.task_done = tasks.filter(status='done').count()
    ctx.task_pending = tasks.filter(status__in=['pending', 'in_progress']).count()
    ctx.task_overdue = tasks.filter(
        due_date__lt=today, status__in=['pending', 'in_progress']
    ).count()
    ctx.task_high_pending = tasks.filter(
        priority='high', status__in=['pending', 'in_progress']
    ).count()

    attendees = event.attendees.all()
    ctx.attendee_total = attendees.count()
    ctx.attendee_pending = attendees.filter(status='pending').count()

    ctx.progress_pct = int((ctx.task_done / ctx.task_total) * 100) if ctx.task_total > 0 else 0

    # Días desde la última actualización del evento o sus tareas
    last_task = tasks.order_by('-updated_at').first()
    if last_task:
        delta = today - last_task.updated_at.date()
        ctx.last_activity_days = delta.days
    else:
        delta = today - event.updated_at.date()
        ctx.last_activity_days = delta.days

    return ctx
