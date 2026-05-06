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


def build_event_context(event, tasks=None, attendees=None):
    """
    Construye y retorna un EventContext para el evento dado.
    Centraliza todos los cálculos de estado del evento.

    Parámetros opcionales:
      tasks     — lista pre-cargada de Task (evita N+1 cuando el queryset
                  ya fue prefetcheado en la vista que llama).
      attendees — lista pre-cargada de Attendee (ídem).
    """
    from django.utils import timezone

    ctx = EventContext(event)
    today = timezone.now().date()

    ctx.has_start_date = event.start_date is not None
    if ctx.has_start_date:
        ctx.days_until = (event.start_date.date() - today).days

    # Si no se pasan listas pre-cargadas, consultar la BD
    if tasks is None:
        tasks = list(event.tasks.all())
    if attendees is None:
        attendees = list(event.attendees.all())

    # Filtrado en Python para aprovechar las listas ya cargadas
    ctx.task_total = len(tasks)
    ctx.task_done = sum(1 for t in tasks if t.status == 'done')
    ctx.task_pending = sum(1 for t in tasks if t.status in ('pending', 'in_progress'))
    ctx.task_overdue = sum(
        1 for t in tasks
        if t.due_date and t.due_date < today and t.status in ('pending', 'in_progress')
    )
    ctx.task_high_pending = sum(
        1 for t in tasks
        if t.priority == 'high' and t.status in ('pending', 'in_progress')
    )

    ctx.attendee_total = len(attendees)
    ctx.attendee_pending = sum(1 for a in attendees if a.status == 'pending')

    ctx.progress_pct = int((ctx.task_done / ctx.task_total) * 100) if ctx.task_total > 0 else 0

    # Días desde la última actualización del evento o sus tareas
    if tasks:
        last_task = max(tasks, key=lambda t: t.updated_at)
        ctx.last_activity_days = (today - last_task.updated_at.date()).days
    else:
        ctx.last_activity_days = (today - event.updated_at.date()).days

    return ctx
