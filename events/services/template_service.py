"""
Template Service — aplica una plantilla a un evento recién creado.

Responsabilidad: dado un Event y un EventTemplate, este servicio:
1. Activa los módulos definidos en la plantilla (filtrable por allowed_modules)
2. Crea las tareas predefinidas con fechas calculadas y auto-asignación al responsable
3. Crea los checklists con sus ítems predefinidos
4. Crea (o recupera) el presupuesto y pre-popula sus ítems desde la plantilla
5. Registra el módulo 'budget' como activo en EventModule

customization (dict opcional):
  excluded_task_pks         – lista de TemplateTask.pk a omitir (preferido)
  excluded_tasks            – lista de títulos de tareas a omitir (compatibilidad)
  excluded_checklist_items  – dict {checklist_title: [item_text, ...]} a omitir
  excluded_budget_item_pks  – lista de TemplateBudgetItem.pk a omitir

Es idempotente: puede llamarse múltiples veces sin duplicar datos.
Toda la operación es atómica — si algo falla, nada se persiste.
"""

from datetime import timedelta, date, datetime
from django.db import transaction


# ── Defaults inteligentes por categoría ──────────────────────────────────────

CATEGORY_DAYS_AHEAD = {
    'business':  30,
    'marketing': 45,
    'academic':  60,
    'creative':  21,
    'social':    14,
}

CATEGORY_DURATION_HOURS = {
    'business':  8,
    'marketing': 4,
    'academic':  3,
    'creative':  3,
    'social':    4,
}


def get_smart_start_date(category):
    from django.utils import timezone
    days = CATEGORY_DAYS_AHEAD.get(category, 30)
    base = timezone.now() + timedelta(days=days)
    return base.replace(minute=0, second=0, microsecond=0)


def get_smart_end_date(start_date, category):
    hours = CATEGORY_DURATION_HOURS.get(category, 4)
    return start_date + timedelta(hours=hours)


# ── Servicio principal ────────────────────────────────────────────────────────

@transaction.atomic
def apply_template_to_event(event, template, owner=None, allowed_modules=None, customization=None):
    """
    Aplica una EventTemplate a un Event existente.

    Parámetros:
        event           – instancia de Event (ya persistida en DB)
        template        – instancia de EventTemplate
        owner           – User opcional; las tareas 'high' se auto-asignan
        allowed_modules – lista de module_type a activar (None = todos)
        customization   – dict con exclusiones on-the-fly:
                            excluded_task_pks: [int]        ← preferido (por PK de TemplateTask)
                            excluded_tasks: [str]            ← compatibilidad (por título)
                            excluded_checklist_items: {checklist_title: [str]}
                            excluded_budget_item_pks: [int]  ← por PK de TemplateBudgetItem
    """
    from events.models import EventModule, TemplateBudgetItem
    from modules.models import Task, Checklist, ChecklistItem, Budget, BudgetItem

    customization = customization or {}

    # Exclusión de tareas: preferir PKs, fallback a títulos para compatibilidad
    excluded_task_pks = set(int(pk) for pk in (customization.get('excluded_task_pks') or []))
    excluded_tasks_by_title = set(customization.get('excluded_tasks') or [])
    excluded_cl_items = customization.get('excluded_checklist_items') or {}
    excluded_budget_pks = set(int(pk) for pk in (customization.get('excluded_budget_item_pks') or []))

    # 1. Activar módulos
    for tm in template.modules.all():
        if allowed_modules is not None and tm.module_type not in allowed_modules:
            continue
        EventModule.objects.get_or_create(
            event=event,
            module_type=tm.module_type,
            defaults={'is_active': True},
        )

    # 2. Crear tareas
    if allowed_modules is None or 'tasks' in allowed_modules:
        existing_titles = set(event.tasks.values_list('title', flat=True))

        tasks_sorted = sorted(
            template.default_tasks.all(),
            key=lambda t: (t.days_before_event if t.days_before_event is not None else -1),
            reverse=True,
        )

        _event_start = event.start_date
        if _event_start is not None:
            if isinstance(_event_start, datetime):
                _event_start = _event_start.date()
            elif not isinstance(_event_start, date):
                from django.utils.dateparse import parse_datetime
                _parsed = parse_datetime(str(_event_start))
                _event_start = _parsed.date() if _parsed else None

        for template_task in tasks_sorted:
            # Exclusión por PK (preciso) o por título (compatibilidad)
            if template_task.pk in excluded_task_pks:
                continue
            if template_task.title in excluded_tasks_by_title:
                continue
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

    # 3. Crear checklists
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
                excluded_in_cl = set(excluded_cl_items.get(checklist_title) or [])
                for item in sorted(items, key=lambda i: i.order):
                    if item.item_text not in excluded_in_cl:
                        ChecklistItem.objects.create(
                            checklist=checklist,
                            text=item.item_text,
                        )

    # 4. Presupuesto: crear si no existe y pre-poblar ítems de la plantilla
    if allowed_modules is None or 'budget' in allowed_modules:
        budget, _ = Budget.objects.get_or_create(
            event=event,
            defaults={'total_budget': 0, 'currency': 'COP'},
        )

        # Overrides de monto: {str(pk): float(amount)}
        budget_item_overrides = {
            str(k): float(v)
            for k, v in (customization.get('budget_item_overrides') or {}).items()
        }

        # Pre-poblar ítems desde la plantilla (idempotente: omite si ya existe con mismo nombre)
        existing_names = set(budget.items.values_list('name', flat=True))
        for tbi in template.default_budget_items.all():
            if tbi.pk in excluded_budget_pks:
                continue
            if tbi.name in existing_names:
                continue
            amount = budget_item_overrides.get(str(tbi.pk), tbi.amount_estimate)
            BudgetItem.objects.create(
                budget=budget,
                name=tbi.name,
                amount=amount,
                item_type=tbi.item_type,
                category=tbi.category,
            )

        # Registrar budget como módulo activo
        EventModule.objects.get_or_create(
            event=event,
            module_type='budget',
            defaults={'is_active': True},
        )
    else:
        # Siempre crear el objeto Budget aunque el módulo no esté activo,
        # para mantener integridad referencial con alertas y métricas.
        Budget.objects.get_or_create(
            event=event,
            defaults={'total_budget': 0, 'currency': 'COP'},
        )
