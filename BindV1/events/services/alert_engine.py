"""
Alert Engine — motor de alertas contextual de BIND.

Analiza todos los eventos activos/borrador del usuario y genera
alertas accionables. Es idempotente: usa alert_key para no duplicar.

Reglas implementadas:
  CRITICAL:
    - Evento inminente (<=3 días) con tareas de alta prioridad pendientes
    - Evento activo (<=7 días) con menos del 50% de tareas completadas
    - Presupuesto superado (usage >= 100%)
  WARNING:
    - Evento sin actividad hace 7+ días y con fecha próxima (<=30 días)
    - Evento con 3+ tareas vencidas
    - Evento inminente con asistentes pendientes de confirmar
    - Presupuesto casi agotado (usage >= 80%)
  INFO:
    - Evento sin fecha de inicio definida con más de 5 tareas
    - Evento activo sin ninguna tarea creada
    - Evento sin presupuesto y con más de 3 tareas (sugiere crear uno)
"""

from django.utils import timezone
from django.urls import reverse
from events.models import Event, EventAlert


def run_alert_engine(user):
    """
    Analiza todos los eventos activos/borrador del usuario
    y genera alertas contextuales.
    Idempotente: usa alert_key para no duplicar.
    """
    today = timezone.now().date()

    events = Event.objects.filter(
        owner=user,
        status__in=['active', 'draft'],
    ).prefetch_related('tasks', 'attendees').select_related('budget')

    for event in events:
        _analyze_event(event, today)


def _analyze_event(event, today):
    """Genera todas las alertas relevantes para un evento específico."""
    tasks = event.tasks.all()
    task_total = tasks.count()
    task_done = tasks.filter(status='done').count()
    task_pending = tasks.filter(status__in=['pending', 'in_progress'])
    task_high_pending = task_pending.filter(priority='high').count()
    task_overdue = tasks.filter(
        due_date__lt=today, status__in=['pending', 'in_progress']
    ).count()

    attendees = event.attendees.all()
    attendee_pending = attendees.filter(status='pending').count()

    days_until = None
    if event.start_date:
        days_until = (event.start_date.date() - today).days

    progress_pct = int((task_done / task_total) * 100) if task_total > 0 else 0

    # Número de semana del año para renovar alertas de stalled semanalmente
    week_number = today.isocalendar()[1]

    # ── CRITICAL ─────────────────────────────────────────────────────────────

    # Evento inminente (<=3 días) con tareas de alta prioridad pendientes
    if days_until is not None and 0 <= days_until <= 3 and task_high_pending > 0:
        key = f"critical-imminent-hp-{event.pk}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'deadline',
                'severity': 'critical',
                'title': 'Evento inminente con tareas críticas sin completar',
                'message': (
                    f"Quedan {task_high_pending} tarea(s) de alta prioridad pendientes. "
                    f"El evento '{event.name}' es en {days_until} día(s)."
                ),
                'action_url': reverse('modules:task_list', kwargs={'event_pk': event.pk}),
                'action_label': 'Ver tareas',
            },
        )

    # Evento activo (<=7 días) con menos del 50% de progreso
    if days_until is not None and 0 <= days_until <= 7 and task_total > 0 and progress_pct < 50:
        key = f"critical-low-progress-{event.pk}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'deadline',
                'severity': 'critical',
                'title': 'El progreso es insuficiente para la fecha del evento',
                'message': (
                    f"Solo el {progress_pct}% de tareas completadas. "
                    f"Quedan {days_until} día(s) para '{event.name}'."
                ),
                'action_url': reverse('modules:task_list', kwargs={'event_pk': event.pk}),
                'action_label': 'Ver tareas',
            },
        )

    # ── WARNING ──────────────────────────────────────────────────────────────

    # Evento sin actividad hace 7+ días con fecha próxima (<=30 días)
    last_task = tasks.order_by('-updated_at').first()
    if last_task:
        last_activity_days = (today - last_task.updated_at.date()).days
    else:
        last_activity_days = (today - event.updated_at.date()).days

    if (last_activity_days >= 7
            and days_until is not None
            and 0 <= days_until <= 30):
        key = f"stalled-{event.pk}-w{week_number}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'stalled',
                'severity': 'warning',
                'title': 'Este evento lleva más de 7 días sin actividad',
                'message': (
                    f"Sin actividad registrada en '{event.name}' hace {last_activity_days} día(s). "
                    f"Faltan {days_until} día(s) para el evento."
                ),
                'action_url': reverse('modules:task_list', kwargs={'event_pk': event.pk}),
                'action_label': 'Retomar',
            },
        )

    # Evento con 3+ tareas vencidas
    if task_overdue >= 3:
        key = f"overdue-tasks-{event.pk}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'deadline',
                'severity': 'warning',
                'title': f'Tienes {task_overdue} tareas vencidas en este evento',
                'message': (
                    f"{task_overdue} tarea(s) de '{event.name}' tienen fecha límite vencida "
                    f"y aún no se han completado."
                ),
                'action_url': reverse('modules:task_list', kwargs={'event_pk': event.pk}),
                'action_label': 'Revisar tareas',
            },
        )

    # Evento inminente (<=7 días) con asistentes pendientes
    if days_until is not None and 0 <= days_until <= 7 and attendee_pending > 0:
        key = f"pending-attendees-{event.pk}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'attendance',
                'severity': 'warning',
                'title': f'{attendee_pending} asistente(s) no han confirmado su asistencia',
                'message': (
                    f"El evento '{event.name}' es en {days_until} día(s) "
                    f"y {attendee_pending} persona(s) aún están como pendientes."
                ),
                'action_url': reverse('modules:attendee_list', kwargs={'event_pk': event.pk}),
                'action_label': 'Ver asistentes',
            },
        )

    # ── INFO ─────────────────────────────────────────────────────────────────

    # Evento sin fecha de inicio con más de 5 tareas
    if not event.start_date and task_total > 5:
        key = f"no-date-{event.pk}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'suggestion',
                'severity': 'info',
                'title': 'Este evento no tiene fecha definida',
                'message': (
                    f"'{event.name}' tiene {task_total} tareas pero sin fecha de inicio. "
                    f"Definir una fecha ayudará a calcular plazos automáticamente."
                ),
                'action_url': reverse('events:event_edit', kwargs={'pk': event.pk}),
                'action_label': 'Definir fecha',
            },
        )

    # Evento activo sin ninguna tarea creada
    if event.status == 'active' and task_total == 0:
        key = f"no-tasks-{event.pk}"
        EventAlert.objects.get_or_create(
            alert_key=key,
            defaults={
                'event': event,
                'alert_type': 'suggestion',
                'severity': 'info',
                'title': 'Este evento no tiene tareas asignadas',
                'message': (
                    f"'{event.name}' está activo pero sin tareas. "
                    f"Agrega tareas para hacer seguimiento del progreso."
                ),
                'action_url': reverse('modules:task_create', kwargs={'event_pk': event.pk}),
                'action_label': 'Agregar tarea',
            },
        )

    # ── PRESUPUESTO ───────────────────────────────────────────────────────────
    _analyze_budget(event, task_total)


def _analyze_budget(event, task_total):
    """Genera alertas de presupuesto para el evento."""
    from django.urls import reverse as _reverse

    try:
        budget = event.budget
    except Exception:
        budget = None

    if budget is not None:
        usage = budget.usage_percentage

        # Presupuesto superado (>= 100%) → critical
        if usage >= 100:
            key = f"budget-critical-{event.pk}"
            EventAlert.objects.get_or_create(
                alert_key=key,
                defaults={
                    'event': event,
                    'alert_type': 'budget',
                    'severity': 'critical',
                    'title': 'El presupuesto ha sido superado',
                    'message': (
                        f"'{event.name}' ha consumido el {usage}% del presupuesto. "
                        f"Gasto actual: {budget.total_spent} {budget.currency} "
                        f"sobre {budget.total_budget} {budget.currency}."
                    ),
                    'action_url': _reverse('modules:budget_detail', kwargs={'event_pk': event.pk}),
                    'action_label': 'Ver presupuesto',
                },
            )
        # Presupuesto casi agotado (>= 80%) → warning
        elif usage >= 80:
            key = f"budget-warning-{event.pk}"
            EventAlert.objects.get_or_create(
                alert_key=key,
                defaults={
                    'event': event,
                    'alert_type': 'budget',
                    'severity': 'warning',
                    'title': 'El presupuesto está casi agotado',
                    'message': (
                        f"'{event.name}' ha consumido el {usage}% del presupuesto. "
                        f"Quedan {budget.remaining} {budget.currency}."
                    ),
                    'action_url': _reverse('modules:budget_detail', kwargs={'event_pk': event.pk}),
                    'action_label': 'Ver presupuesto',
                },
            )
    else:
        # Sin presupuesto y con más de 3 tareas → info (sugiere crear uno)
        if task_total > 3:
            key = f"budget-suggest-{event.pk}"
            EventAlert.objects.get_or_create(
                alert_key=key,
                defaults={
                    'event': event,
                    'alert_type': 'budget',
                    'severity': 'info',
                    'title': 'Considera crear un presupuesto para este evento',
                    'message': (
                        f"'{event.name}' tiene {task_total} tareas pero no tiene "
                        f"presupuesto definido. Llevar un registro de gastos ayuda "
                        f"a evitar sorpresas."
                    ),
                    'action_url': _reverse('modules:budget_detail', kwargs={'event_pk': event.pk}),
                    'action_label': 'Crear presupuesto',
                },
            )
