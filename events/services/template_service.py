"""
Template Service — aplica una plantilla a un evento recién creado.

Responsabilidad: dado un Event y un EventTemplate, este servicio:
1. Activa los módulos definidos en la plantilla
2. Crea las tareas predefinidas con fechas calculadas y auto-asignación
3. Crea los checklists con sus ítems predefinidos
4. Crea un presupuesto vacío listo para usar

Es idempotente: puede llamarse múltiples veces sin duplicar datos.
"""

from datetime import timedelta


# ── Defaults inteligentes por categoría ──────────────────────────────────────

# Días de anticipación para calcular start_date automático
CATEGORY_DAYS_AHEAD = {
    'business':  30,
    'marketing': 45,
    'academic':  60,
    'creative':  21,
    'social':    14,
}

# Duración predeterminada del evento en horas
CATEGORY_DURATION_HOURS = {
    'business':  8,
    'marketing': 4,
    'academic':  3,
    'creative':  3,
    'social':    4,
}


def get_smart_start_date(category):
    """Retorna un start_date sensato según la categoría de la plantilla."""
    from django.utils import timezone
    days = CATEGORY_DAYS_AHEAD.get(category, 30)
    # Redondear al próximo lunes a las 09:00 para mayor coherencia
    base = timezone.now() + timedelta(days=days)
    # Redondear a la hora (sin minutos ni segundos)
    base = base.replace(minute=0, second=0, microsecond=0)
    return base


def get_smart_end_date(start_date, category):
    """Retorna un end_date sensato a partir del start_date."""
    hours = CATEGORY_DURATION_HOURS.get(category, 4)
    return start_date + timedelta(hours=hours)


# ── Servicio principal ────────────────────────────────────────────────────────

def apply_template_to_event(event, template, owner=None):
    """
    Aplica una EventTemplate a un Event existente.

    Parámetros:
        event    – instancia de Event (ya persistida en DB)
        template – instancia de EventTemplate
        owner    – User opcional; si se provee, las tareas de prioridad 'high'
                   se auto-asignan a este usuario para eliminar el paso manual

    Comportamiento de cero fricciones:
    - Módulos activados automáticamente según la plantilla
    - Tareas creadas en orden cronológico (por days_before_event DESC)
    - Tareas 'high' auto-asignadas al owner del evento
    - Checklists creados con ítems predefinidos
    - Presupuesto vacío creado y listo para usar
    """
    from events.models import EventModule
    from modules.models import Task, Checklist, ChecklistItem, Budget

    # 1. Activar módulos definidos en la plantilla
    for tm in template.modules.all():
        EventModule.objects.get_or_create(
            event=event,
            module_type=tm.module_type,
            defaults={'is_active': True},
        )

    # 2. Crear tareas predefinidas (idempotente por título)
    #    Orden cronológico: mayor days_before_event primero = tarea más temprana en el tiempo
    existing_titles = set(event.tasks.values_list('title', flat=True))

    tasks_sorted = sorted(
        template.default_tasks.all(),
        key=lambda t: (t.days_before_event if t.days_before_event is not None else -1),
        reverse=True,
    )

    for template_task in tasks_sorted:
        if template_task.title in existing_titles:
            continue

        due_date = None
        if event.start_date and template_task.days_before_event is not None:
            due_date = event.start_date.date() - timedelta(days=template_task.days_before_event)

        # Auto-asignar tareas críticas al owner para eliminación de fricciones
        assigned_to = owner if (owner and template_task.priority == 'high') else None

        Task.objects.create(
            event=event,
            title=template_task.title,
            description=template_task.description,
            priority=template_task.priority,
            status='pending',
            due_date=due_date,
            assigned_to=assigned_to,
        )

    # 3. Crear checklists predefinidos con sus ítems
    checklist_items = template.default_checklist_items.all()
    checklists_map = {}
    for item in checklist_items:
        checklists_map.setdefault(item.checklist_title, []).append(item)

    for checklist_title, items in checklists_map.items():
        checklist, created = Checklist.objects.get_or_create(
            event=event,
            title=checklist_title,
        )
        if created:
            for item in sorted(items, key=lambda i: i.order):
                ChecklistItem.objects.create(
                    checklist=checklist,
                    text=item.item_text,
                )

    # 4. Crear presupuesto vacío (idempotente con OneToOne)
    Budget.objects.get_or_create(
        event=event,
        defaults={
            'total_budget': 0,
            'currency': 'COP',
        }
    )
