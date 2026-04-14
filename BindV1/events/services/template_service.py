"""
Template Service — aplica una plantilla a un evento recién creado.

Responsabilidad: dado un Event y un EventTemplate, este servicio:
1. Activa los módulos definidos en la plantilla
2. Crea las tareas predefinidas con fechas calculadas
3. Crea los checklists con sus ítems predefinidos
4. Crea un presupuesto vacío listo para usar

Es idempotente: puede llamarse múltiples veces sin duplicar datos.
"""

from datetime import timedelta


def apply_template_to_event(event, template):
    """
    Aplica una EventTemplate a un Event existente.

    Activa módulos, crea tareas y checklists predefinidos,
    y crea un presupuesto vacío. Idempotente.
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
    existing_titles = set(event.tasks.values_list('title', flat=True))
    for template_task in template.default_tasks.all():
        if template_task.title in existing_titles:
            continue

        due_date = None
        if event.start_date and template_task.days_before_event is not None:
            due_date = event.start_date.date() - timedelta(days=template_task.days_before_event)

        Task.objects.create(
            event=event,
            title=template_task.title,
            description=template_task.description,
            priority=template_task.priority,
            status='pending',
            due_date=due_date,
        )

    # 3. Crear checklists predefinidos con sus ítems
    # Agrupar ítems por checklist_title
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
