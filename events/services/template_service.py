"""
Template Service — aplica una plantilla a un evento recién creado.

Responsabilidad: dado un Event y un EventTemplate, este servicio:
1. Activa los módulos definidos en la plantilla (filtrable por allowed_modules)
2. Crea las tareas predefinidas con fechas calculadas y auto-asignación
3. Crea los checklists con sus ítems predefinidos
4. Crea un presupuesto vacío listo para usar

Es idempotente: puede llamarse múltiples veces sin duplicar datos.
Toda la operación es atómica — si algo falla, nada se persiste.
"""

from datetime import timedelta, date, datetime
from django.db import transaction


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

@transaction.atomic
def apply_template_to_event(event, template, owner=None, allowed_modules=None):
    """
    Aplica una EventTemplate a un Event existente.

    Parámetros:
        event           – instancia de Event (ya persistida en DB)
        template        – instancia de EventTemplate
        owner           – User opcional; si se provee, las tareas 'high' se auto-asignan
        allowed_modules – lista de module_type a activar (None = todos los de la plantilla)

    Toda la operación es atómica: si cualquier paso falla nada se persiste.
    """
    from events.models import EventModule
    from modules.models import Task, Checklist, ChecklistItem, Budget

    # 1. Activar módulos — filtrados por allowed_modules si se indicó
    for tm in template.modules.all():
        if allowed_modules is not None and tm.module_type not in allowed_modules:
            continue
        EventModule.objects.get_or_create(
            event=event,
            module_type=tm.module_type,
            defaults={'is_active': True},
        )

    # 2. Crear tareas (solo si el módulo 'tasks' está permitido)
    if allowed_modules is None or 'tasks' in allowed_modules:
        existing_titles = set(event.tasks.values_list('title', flat=True))

        tasks_sorted = sorted(
            template.default_tasks.all(),
            key=lambda t: (t.days_before_event if t.days_before_event is not None else -1),
            reverse=True,
        )

        # Normalizar event.start_date a date independientemente del tipo recibido
        _event_start = event.start_date
        if _event_start is not None:
            if isinstance(_event_start, datetime):
                _event_start = _event_start.date()
            elif isinstance(_event_start, date):
                pass
            else:
                from django.utils.dateparse import parse_datetime
                _parsed = parse_datetime(str(_event_start))
                _event_start = _parsed.date() if _parsed else None

        for template_task in tasks_sorted:
            if template_task.title in existing_titles:
                continue

            due_date = None
            if _event_start and template_task.days_before_event is not None:
                due_date = _event_start - timedelta(days=template_task.days_before_event)

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

    # 3. Crear checklists (solo si el módulo 'checklist' está permitido)
    if allowed_modules is None or 'checklist' in allowed_modules:
        checklists_map = {}
        for item in template.default_checklist_items.all():
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

    # 4. Crear presupuesto vacío
    Budget.objects.get_or_create(
        event=event,
        defaults={
            'total_budget': 0,
            'currency': 'COP',
        }
    )
