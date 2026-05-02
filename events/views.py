import json

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q, Sum, F
from django.db.models.functions import Coalesce

from django.db import models as db_models
from .models import Event, EventTemplate, EventModule, TemplateModule, EventAlert, EngineMetrics
from .stats import compute_user_stats
from modules.models import Task, File, Checklist
from datetime import timedelta
import calendar as cal_module
from datetime import date as date_cls


# ── Helper: serializa plantillas a JSON para el frontend ─────────────────────

def _build_templates_json(templates_qs):
    data = {}
    for tmpl in templates_qs:
        checklists = {}
        for item in tmpl.default_checklist_items.order_by('checklist_title', 'order'):
            checklists.setdefault(item.checklist_title, []).append(item.item_text)
        data[str(tmpl.pk)] = {
            'name':        tmpl.name,
            'description': tmpl.description,
            'category':    tmpl.category,
            'taskCount':   tmpl.default_tasks.count(),
            'tasks': [
                {
                    'pk':               t.pk,
                    'title':            t.title,
                    'priority':         t.priority,
                    'days_before_event': t.days_before_event,
                }
                for t in tmpl.default_tasks.order_by('order')
            ],
            'checklists': checklists,
            'modules':    list(tmpl.modules.values_list('module_type', flat=True)),
            'budgetItems': [
                {
                    'pk':       bi.pk,
                    'name':     bi.name,
                    'amount':   float(bi.amount_estimate),
                    'type':     bi.item_type,
                    'category': bi.get_category_display(),
                }
                for bi in tmpl.default_budget_items.order_by('order')
            ],
        }
    return json.dumps(data, ensure_ascii=False)


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    import logging
    from events.engine import run_engine_for_user
    try:
        engine_output = run_engine_for_user(request.user)
    except Exception as e:
        logging.getLogger(__name__).error(f"Engine error: {e}")
        engine_output = {
            'event_scores': {},
            'event_contexts': {},
            'all_decisions': [],
            'dashboard_summary': {
                'critical_count': 0, 'events_at_risk': 0,
                'events_on_track': 0, 'needs_attention': False,
            },
        }

    stats = compute_user_stats(request.user)

    # Eventos activos con presupuesto definido (para widget de salud presupuestaria).
    # total_spent y total_budget se anotan en SQL para evitar N+1:
    # budget.total_spent es una @property que hace Sum('items__amount') por cada evento.
    budget_events = (
        Event.objects.filter(owner=request.user, status__in=['active', 'draft'])
        .select_related('budget')
        .filter(budget__isnull=False)
        .annotate(
            total_spent=Coalesce(Sum('budget__items__amount'), 0),
            total_budget=F('budget__total_budget'),
        )
        .order_by('-updated_at')[:5]
    )

    # AlertsDB — usadas para el panel de decisiones con botón dismiss
    alerts = EventAlert.objects.filter(
        event__owner=request.user,
        is_dismissed=False,
    ).select_related('event').order_by(
        db_models.Case(
            db_models.When(severity='critical', then=0),
            db_models.When(severity='warning', then=1),
            default=2,
            output_field=db_models.IntegerField(),
        ),
        '-created_at',
    )[:5]

    context = {
        'active_events_count': stats['active_events'],
        'total_events':        stats['total_events'],
        'pending_tasks':       stats['pending_tasks'],
        'tasks_today':         stats.get('tasks_today', 0),
        'featured_event':      stats.get('featured_event'),
        'upcoming_events':     stats.get('upcoming_events', [])[:5],
        'urgent_tasks':        stats.get('urgent_tasks')[:3] if stats.get('urgent_tasks') is not None else [],
        'recent_events':       stats.get('recent_events', [])[:6],
        'weekly_activity':     stats.get('weekly_activity', []),
        'today_label':         stats.get('today_label', ''),
        'max_tasks_day':       stats.get('max_tasks_day', 0),
        'high_tasks':          stats.get('high_tasks', 0),
        'medium_tasks':        stats.get('medium_tasks', 0),
        'low_tasks':           stats.get('low_tasks', 0),
        'overdue_tasks':       stats.get('overdue_tasks', []),
        'alerts':              alerts,
        'engine_output':       engine_output,
        'engine_summary':      engine_output['dashboard_summary'],
        'engine_decisions':    engine_output['all_decisions'],
        'budget_events':       budget_events,
    }
    return render(request, 'events/dashboard.html', context)


def _get_event_score(event):
    """Retorna (health_score, risk_level) actuales del evento. Silencia errores."""
    try:
        from events.engine.context import build_event_context
        from events.engine.scorer import score_event
        ctx = build_event_context(event)
        s = score_event(ctx)
        return s.health_score, s.risk_level
    except Exception:
        return 0, 0


@login_required
def alert_dismiss(request, pk):
    """Marca una alerta como dismissed via POST. Registra métrica de descarte."""
    if request.method == 'POST':
        alert = get_object_or_404(EventAlert, pk=pk, event__owner=request.user)
        alert.is_dismissed = True
        alert.save()
        try:
            health, risk = _get_event_score(alert.event)
            EngineMetrics.objects.get_or_create(
                decision_key=alert.alert_key,
                defaults={
                    'decision_type': alert.alert_type,
                    'event': alert.event,
                    'user': request.user,
                    'health_score_at_decision': health,
                    'risk_level_at_decision': risk,
                    'user_acted': False,
                    'action_taken': 'dismissed',
                }
            )
        except Exception:
            pass
        # Validar next: solo rutas relativas del mismo sitio
        next_url = request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('events:dashboard')
    return redirect('events:dashboard')


@login_required
def alert_action(request, pk):
    """
    Intermedia entre la alerta y su destino.
    Registra que el usuario siguió la acción (user_acted=True) y redirige.
    """
    alert = get_object_or_404(EventAlert, pk=pk, event__owner=request.user)
    alert.is_read = True
    alert.save()
    try:
        health, risk = _get_event_score(alert.event)
        EngineMetrics.objects.create(
            decision_key=alert.alert_key,
            decision_type=alert.alert_type,
            event=alert.event,
            user=request.user,
            health_score_at_decision=health,
            risk_level_at_decision=risk,
            user_acted=True,
            action_taken='followed_action',
        )
    except Exception:
        pass
    if alert.action_url:
        return redirect(alert.action_url)
    return redirect('events:dashboard')


# ─────────────────────────────────────────────
#  LISTA DE PROYECTOS (todos los eventos)
# ─────────────────────────────────────────────

@login_required
def event_list(request):
    """
    Lista TODOS los proyectos/eventos del usuario.
    Vista tipo gestor: muestra todo con filtros, búsqueda y paginación.
    """
    from django.core.paginator import Paginator
    from events.engine.context import build_event_context
    from events.engine.scorer import score_event

    events_qs = Event.objects.filter(owner=request.user).order_by('-updated_at').prefetch_related('tasks', 'attendees')

    status_filter = request.GET.get('status', '')
    if status_filter:
        events_qs = events_qs.filter(status=status_filter)

    q = request.GET.get('q', '')
    if q:
        events_qs = events_qs.filter(name__icontains=q)

    # Anotar health score y calcular task_progress en Python
    # Se pasan las listas pre-cargadas para evitar N+1 queries por evento
    events_list = list(events_qs)
    for event in events_list:
        try:
            prefetched_tasks = list(event.tasks.all())
            prefetched_attendees = list(event.attendees.all())
            ctx = build_event_context(event, tasks=prefetched_tasks, attendees=prefetched_attendees)
            escore = score_event(ctx)
            event.health_score = escore.health_score
            event.health_label = escore.health_label
            event.risk_label = escore.risk_label
            total_t = ctx.task_total
            done_t = ctx.task_done
            event.task_progress = int((done_t / total_t) * 100) if total_t > 0 else 0
        except Exception:
            event.health_score = None
            event.health_label = None
            event.risk_label = None
            event.task_progress = 0

    paginator = Paginator(events_list, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'events':         page_obj,
        'page_obj':       page_obj,
        'status_filter':  status_filter,
        'q':              q,
        'status_choices': Event.STATUS_CHOICES,
    }
    return render(request, 'events/event_list.html', context)


# ─────────────────────────────────────────────
#  EVENTOS EN CURSO (vista de eventos activos)
# ─────────────────────────────────────────────

@login_required
def eventos_en_curso(request):
    """
    Muestra solo los eventos activos/en progreso actualmente.
    Vista tipo timeline/calendario: enfocado en lo que está pasando ahora.
    """
    today = timezone.now().date()

    # Eventos activos (en progreso)
    active_events = Event.objects.filter(
        owner=request.user,
        status='active'
    ).order_by('start_date')

    # Eventos en revisión (borrador)
    draft_events = Event.objects.filter(
        owner=request.user,
        status='draft'
    ).order_by('-updated_at')

    # Eventos completados recientemente
    completed_events = Event.objects.filter(
        owner=request.user,
        status='completed'
    ).order_by('-updated_at')[:5]

    # Calcular días restantes y progreso para cada evento activo
    for event in active_events:
        if event.start_date:
            delta = event.start_date.date() - today
            event.days_until = max(delta.days, 0)
        else:
            event.days_until = None
        # Calcular progreso de tareas
        total = event.tasks.count()
        done = event.tasks.filter(status='done').count()
        event.task_progress = int((done / total * 100)) if total > 0 else 0

    context = {
        'active_events': active_events,
        'draft_events': draft_events,
        'completed_events': completed_events,
        'today': today,
    }
    return render(request, 'events/eventos_en_curso.html', context)


# ─────────────────────────────────────────────
#  DETALLE DE EVENTO
# ─────────────────────────────────────────────

@login_required
def event_detail(request, pk):
    event = get_object_or_404(
        Event.objects.select_related('budget', 'template', 'owner'),
        pk=pk, owner=request.user,
    )

    # Módulos activos de este evento
    active_modules = event.modules.filter(is_active=True).values_list('module_type', flat=True)

    # Progreso de tareas
    total_tasks = event.tasks.count()
    done_tasks  = event.tasks.filter(status='done').count()
    task_progress = int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    # Días restantes — sin clampear a 0 para poder mostrar "Finalizado" en template
    today = timezone.now().date()
    days_until = None
    if event.start_date:
        days_until = (event.start_date.date() - today).days

    # Preparar datos de módulos con progreso
    tasks_preview = event.tasks.all().order_by('-created_at')[:5]
    checklists_preview = []
    for cl in event.checklists.all()[:3]:
        cl_data = cl
        cl_data.progress = cl.progress()
        checklists_preview.append(cl_data)
    files_preview = event.files.all().order_by('-uploaded_at')[:5]
    attendees_preview = event.attendees.all()[:5]

    try:
        from events.engine.context import build_event_context
        from events.engine.scorer import score_event
        engine_ctx = build_event_context(event)
        engine_score = score_event(engine_ctx)
    except Exception:
        engine_score = None

    context = {
        'event':               event,
        'active_modules':      list(active_modules),
        'task_progress':       task_progress,
        'days_until':          days_until,
        'tasks_preview':       tasks_preview,
        'checklists_preview':  checklists_preview,
        'files_preview':       files_preview,
        'attendees_preview':   attendees_preview,
        'engine_score':        engine_score,
    }
    return render(request, 'events/event_detail.html', context)


# ─────────────────────────────────────────────
#  GESTIÓN DE MÓDULOS DEL EVENTO
# ─────────────────────────────────────────────

@login_required
def event_modules_manage(request, pk):
    """
    Vista para activar/desactivar módulos de un evento.
    Solo muestra módulos disponibles, el usuario decide cuáles activar.
    """
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    # Módulos actualmente activos
    active_modules = list(event.modules.filter(is_active=True).values_list('module_type', flat=True))

    # Todos los módulos disponibles
    all_module_choices = EventModule.MODULE_CHOICES

    if request.method == 'POST':
        # Módulos seleccionados en el POST
        selected_modules = request.POST.getlist('modules')

        # Desactivar todos primero
        event.modules.update(is_active=False)

        # Activar seleccionados
        for module_type in selected_modules:
            module, created = EventModule.objects.get_or_create(
                event=event,
                module_type=module_type,
                defaults={'is_active': True}
            )
            if not created:
                module.is_active = True
                module.save()

        messages.success(request, 'Módulos actualizados correctamente.')
        return redirect('events:event_detail', pk=event.pk)

    context = {
        'event': event,
        'active_modules': active_modules,
        'all_module_choices': all_module_choices,
    }
    return render(request, 'events/event_modules_manage.html', context)


# ─────────────────────────────────────────────
#  CREAR EVENTO
# ─────────────────────────────────────────────

@login_required
def event_create(request):
    from events.services.template_service import (
        apply_template_to_event, get_smart_start_date, get_smart_end_date
    )
    templates = EventTemplate.objects.prefetch_related(
        'modules', 'default_tasks', 'default_checklist_items', 'default_budget_items'
    ).all()

    if request.method == 'POST':
        name             = request.POST.get('name', '').strip()
        description      = request.POST.get('description', '').strip()
        location         = request.POST.get('location', '').strip()
        status           = request.POST.get('status', 'draft')
        start_date       = request.POST.get('start_date') or None
        end_date         = request.POST.get('end_date') or None
        template_id      = request.POST.get('template_id') or None
        selected_modules = request.POST.getlist('modules')

        # Personalización on-the-fly enviada desde el panel lateral del formulario
        customization = {}
        customization_raw = request.POST.get('template_customization', '')
        if customization_raw:
            try:
                customization = json.loads(customization_raw)
            except (json.JSONDecodeError, ValueError):
                pass

        if not name:
            messages.error(request, 'El nombre del evento es obligatorio.')
            return render(request, 'events/event_form.html', {
                'templates':      templates,
                'templates_json': _build_templates_json(templates),
            })

        template = None
        if template_id:
            template = EventTemplate.objects.prefetch_related(
                'modules', 'default_tasks', 'default_checklist_items', 'default_budget_items'
            ).filter(pk=template_id).first()

        if template:
            if not description:
                description = template.description
            if not start_date:
                start_date = get_smart_start_date(template.category)
            if not end_date and start_date:
                end_date = get_smart_end_date(
                    start_date if hasattr(start_date, 'hour')
                    else timezone.datetime.fromisoformat(str(start_date)),
                    template.category,
                )
            if status == 'draft':
                status = 'active'

        with transaction.atomic():
            event = Event.objects.create(
                name=name,
                description=description,
                location=location,
                status=status,
                start_date=start_date,
                end_date=end_date,
                owner=request.user,
                template=template,
            )

            if template:
                allowed = selected_modules if selected_modules else None
                apply_template_to_event(
                    event, template,
                    owner=request.user,
                    allowed_modules=allowed,
                    customization=customization,
                )
                task_count = event.tasks.count()
                messages.success(
                    request,
                    f'Proyecto "{event.name}" creado con {task_count} tarea{"s" if task_count != 1 else ""}.'
                )
            else:
                modules_to_activate = selected_modules if selected_modules else [
                    'tasks', 'attendees', 'checklist', 'files'
                ]
                for module_type in modules_to_activate:
                    EventModule.objects.get_or_create(
                        event=event,
                        module_type=module_type,
                        defaults={'is_active': True},
                    )
                messages.success(request, f'Evento "{event.name}" creado.')

        return redirect('events:event_detail', pk=event.pk)

    selected_template = None
    template_param = request.GET.get('template')
    if template_param:
        selected_template = EventTemplate.objects.filter(pk=template_param).first()

    return render(request, 'events/event_form.html', {
        'templates':         templates,
        'templates_json':    _build_templates_json(templates),
        'selected_template': selected_template,
    })


# ─────────────────────────────────────────────
#  CREAR PROYECTO INSTANTÁNEO (CERO FRICCIONES)
# ─────────────────────────────────────────────

@login_required
def quick_create_from_template(request, template_id):
    """
    Crea un proyecto completo desde una plantilla con un solo clic.
    Acepta 'name' (opcional) y 'template_customization' (JSON, opcional).
    """
    from events.services.template_service import (
        apply_template_to_event, get_smart_start_date, get_smart_end_date
    )

    if request.method != 'POST':
        return redirect('events:template_list')

    template = get_object_or_404(EventTemplate, pk=template_id)

    name = request.POST.get('name', '').strip()
    if not name:
        name = f"{template.name} — {timezone.now().strftime('%d/%m/%Y')}"

    customization = {}
    customization_raw = request.POST.get('template_customization', '')
    if customization_raw:
        try:
            customization = json.loads(customization_raw)
        except (json.JSONDecodeError, ValueError):
            pass

    start_date = get_smart_start_date(template.category)
    end_date   = get_smart_end_date(start_date, template.category)

    with transaction.atomic():
        event = Event.objects.create(
            name=name,
            description=template.description,
            status='active',
            start_date=start_date,
            end_date=end_date,
            owner=request.user,
            template=template,
        )
        apply_template_to_event(event, template, owner=request.user, customization=customization)

    # Modificación permanente de la plantilla si el usuario lo solicitó
    if request.POST.get('modify_template') == '1' and customization:
        from events.models import TemplateTask, TemplateBudgetItem, TemplateChecklistItem
        exc_task_pks   = customization.get('excluded_task_pks', [])
        exc_budget_pks = customization.get('excluded_budget_item_pks', [])
        exc_cl_items   = customization.get('excluded_checklist_items', {})
        if exc_task_pks:
            TemplateTask.objects.filter(template=template, pk__in=exc_task_pks).delete()
        if exc_budget_pks:
            TemplateBudgetItem.objects.filter(template=template, pk__in=exc_budget_pks).delete()
        for cl_title, items in exc_cl_items.items():
            if items:
                TemplateChecklistItem.objects.filter(
                    template=template, checklist_title=cl_title, item_text__in=items
                ).delete()

    task_count = event.tasks.count()
    messages.success(
        request,
        f'Proyecto "{event.name}" creado — {task_count} tarea{"s" if task_count != 1 else ""}, '
        f'inicio programado para el {start_date.strftime("%d/%m/%Y")}.'
    )
    return redirect('events:event_detail', pk=event.pk)


# ─────────────────────────────────────────────
#  EDITAR EVENTO
# ─────────────────────────────────────────────

@login_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == 'POST':
        previous_status = event.status
        event.name        = request.POST.get('name', event.name).strip()
        event.description = request.POST.get('description', '').strip()
        event.location    = request.POST.get('location', '').strip()
        event.status      = request.POST.get('status', event.status)
        event.start_date  = request.POST.get('start_date') or None
        event.end_date    = request.POST.get('end_date') or None
        event.save()

        # Flujo de cierre: si el evento acaba de marcarse como completado
        if previous_status != 'completed' and event.status == 'completed':
            completion_summary = _handle_event_completion(event, request.user)
            messages.success(
                request,
                f'Evento "{event.name}" completado. '
                f'{completion_summary["tasks_done"]}/{completion_summary["tasks_total"]} tareas, '
                f'{completion_summary["attendees_confirmed"]} asistentes confirmados.'
            )
            return redirect('events:event_detail', pk=event.pk)

        messages.success(request, f'Evento "{event.name}" actualizado.')
        return redirect('events:event_detail', pk=event.pk)

    return render(request, 'events/event_form.html', {
        'event':    event,
        'object':   event,
        'templates': EventTemplate.objects.all(),
    })


def _handle_event_completion(event, user):
    """
    Ejecuta el flujo de cierre cuando un evento pasa a status='completed':
    1. Auto-dismiss todas las alertas activas (idempotente).
    2. Registra EngineMetrics con action_taken='event_completed'.
    3. Retorna resumen de cierre para mostrar en el mensaje.
    """
    # 1. Descartar todas las alertas activas del evento
    EventAlert.objects.filter(event=event, is_dismissed=False).update(is_dismissed=True)

    # 2. Registrar métricas de cierre
    try:
        from events.engine.context import build_event_context
        from events.engine.scorer import score_event
        ctx = build_event_context(event)
        score = score_event(ctx)
        health, risk = score.health_score, score.risk_level
    except Exception:
        ctx = None
        health, risk = 0, 0

    try:
        EngineMetrics.objects.create(
            decision_key=f"event_completed-{event.pk}",
            decision_type='event_completed',
            event=event,
            user=user,
            health_score_at_decision=health,
            risk_level_at_decision=risk,
            user_acted=True,
            action_taken='event_completed',
            issue_resolved=True,
        )
    except Exception:
        pass

    # 3. Construir resumen
    tasks_total = event.tasks.count()
    tasks_done = event.tasks.filter(status='done').count()
    budget_info = None
    try:
        b = event.budget
        budget_info = {'total_budget': b.total_budget, 'total_spent': b.total_spent,
                       'usage_pct': b.usage_percentage, 'currency': b.currency}
    except Exception:
        pass

    from modules.models import Attendee
    attendees_confirmed = event.attendees.filter(status='confirmed').count()

    return {
        'tasks_total': tasks_total,
        'tasks_done': tasks_done,
        'budget': budget_info,
        'attendees_confirmed': attendees_confirmed,
    }


# ─────────────────────────────────────────────
#  ELIMINAR EVENTO
# ─────────────────────────────────────────────

@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == 'POST':
        name = event.name
        event.delete()
        messages.success(request, f'Evento "{name}" eliminado.')
        return redirect('events:event_list')

    return render(request, 'events/event_confirm_delete.html', {'event': event})


# ─────────────────────────────────────────────
#  PLANTILLAS
# ─────────────────────────────────────────────

@login_required
def global_search(request):
    """Búsqueda global: eventos, tareas y asistentes del usuario."""
    q = request.GET.get('q', '').strip()

    if len(q) < 2:
        return render(request, 'events/search_results.html', {
            'q': q,
            'too_short': True,
        })

    user = request.user
    from modules.models import Attendee

    events_results = Event.objects.filter(
        owner=user
    ).filter(
        db_models.Q(name__icontains=q) | db_models.Q(description__icontains=q)
    ).order_by('-updated_at')[:6]

    tasks_results = Task.objects.filter(
        event__owner=user,
        title__icontains=q
    ).select_related('event').order_by('-created_at')[:6]

    attendees_results = Attendee.objects.filter(
        event__owner=user
    ).filter(
        db_models.Q(name__icontains=q) | db_models.Q(email__icontains=q)
    ).select_related('event').order_by('name')[:6]

    total = (
        events_results.count()
        + tasks_results.count()
        + attendees_results.count()
    )

    return render(request, 'events/search_results.html', {
        'q': q,
        'events_results': events_results,
        'tasks_results': tasks_results,
        'attendees_results': attendees_results,
        'total': total,
    })


@login_required
def template_list(request):
    category = request.GET.get('category', '')
    templates = EventTemplate.objects.prefetch_related(
        'modules', 'default_tasks', 'default_checklist_items'
    ).all()
    if category:
        templates = templates.filter(category=category)

    context = {
        'templates':        templates,
        'templates_json':   _build_templates_json(templates),
        'category_filter':  category,
        'category_choices': EventTemplate.CATEGORY_CHOICES,
    }
    return render(request, 'events/template_list.html', context)


@login_required
def template_preview_json(request, template_id):
    """Devuelve los datos de una plantilla como JSON para modales y paneles."""
    template = get_object_or_404(EventTemplate, pk=template_id)
    checklists = {}
    for item in template.default_checklist_items.order_by('checklist_title', 'order'):
        checklists.setdefault(item.checklist_title, []).append(item.item_text)
    return JsonResponse({
        'id':               template.pk,
        'name':             template.name,
        'description':      template.description,
        'category':         template.category,
        'category_display': template.get_category_display(),
        'tasks': list(template.default_tasks.order_by('order').values(
            'title', 'priority', 'days_before_event'
        )),
        'checklists': checklists,
        'modules':    list(template.modules.values_list('module_type', flat=True)),
    })
@login_required
def report_view(request):
    stats = compute_user_stats(request.user)
    return render(request, 'events/report.html', stats)


@login_required
def calendar_view(request):
    """
    Calendario estilo Google Calendar.
    Entrega TODOS los eventos y tareas del usuario al template;
    el JS se encarga de renderizar mes / semana / día.
    """
    from datetime import date as date_cls
    today = timezone.now().date()
 
    # Todos los eventos del usuario, anotados con progreso de tareas
    all_events_qs = Event.objects.filter(
        owner=request.user
    ).select_related('template', 'budget').annotate(
        ev_total_tasks=Count('tasks', distinct=True),
        ev_done_tasks=Count('tasks', filter=Q(tasks__status='done'), distinct=True)
    ).order_by('start_date')

    all_events = list(all_events_qs)
    for ev in all_events:
        total = ev.ev_total_tasks
        done  = ev.ev_done_tasks
        ev.task_progress_pct = int(done / total * 100) if total > 0 else 0
        try:
            ev.budget_pct   = ev.budget.usage_percentage
            ev.budget_used  = float(ev.budget.total_spent)
            ev.budget_total = float(ev.budget.total_budget)
        except Exception:
            ev.budget_pct   = 0
            ev.budget_used  = 0.0
            ev.budget_total = 0.0

    # Todas las tareas pendientes / en progreso con fecha límite
    all_tasks = Task.objects.filter(
        event__owner=request.user,
        due_date__isnull=False,
    ).select_related('event').order_by('due_date')

    # Próximos 5 eventos para el panel lateral
    upcoming_events = Event.objects.filter(
        owner=request.user,
        start_date__date__gte=today,
        status__in=['active', 'draft'],
    ).order_by('start_date')[:5]

    context = {
        'all_events':      all_events,
        'all_tasks':       all_tasks,
        'upcoming_events': upcoming_events,
        'status_choices':  Event.STATUS_CHOICES,
        'today':           today,
    }
    return render(request, 'events/calendar.html', context)
 