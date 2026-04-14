from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q

from django.db import models as db_models
from .models import Event, EventTemplate, EventModule, TemplateModule, EventAlert, EngineMetrics
from .stats import compute_user_stats
from modules.models import Task, File, Checklist
from datetime import timedelta
import calendar as cal_module
from datetime import date as date_cls


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
    }
    return render(request, 'events/dashboard.html', context)


@login_required
def alert_dismiss(request, pk):
    """Marca una alerta como dismissed via POST. Registra métrica de descarte."""
    if request.method == 'POST':
        alert = get_object_or_404(EventAlert, pk=pk, event__owner=request.user)
        alert.is_dismissed = True
        alert.save()
        try:
            EngineMetrics.objects.get_or_create(
                decision_key=alert.alert_key,
                defaults={
                    'decision_type': alert.alert_type,
                    'event': alert.event,
                    'user': request.user,
                    'health_score_at_decision': 0,
                    'risk_level_at_decision': 0,
                    'user_acted': False,
                    'action_taken': 'dismissed',
                }
            )
        except Exception:
            pass
        return redirect(request.POST.get('next', 'events:dashboard'))
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
        EngineMetrics.objects.create(
            decision_key=alert.alert_key,
            decision_type=alert.alert_type,
            event=alert.event,
            user=request.user,
            health_score_at_decision=0,
            risk_level_at_decision=0,
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

    events_qs = Event.objects.filter(owner=request.user).order_by('-updated_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        events_qs = events_qs.filter(status=status_filter)

    q = request.GET.get('q', '')
    if q:
        events_qs = events_qs.filter(name__icontains=q)

    # Anotar health score y calcular task_progress en Python
    events_list = list(events_qs)
    for event in events_list:
        try:
            ctx = build_event_context(event)
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
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    # Módulos activos de este evento
    active_modules = event.modules.filter(is_active=True).values_list('module_type', flat=True)

    # Progreso de tareas
    total_tasks = event.tasks.count()
    done_tasks  = event.tasks.filter(status='done').count()
    task_progress = int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    # Días restantes
    today = timezone.now().date()
    days_until = None
    if event.start_date:
        delta = event.start_date.date() - today
        days_until = max(delta.days, 0)

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
    templates = EventTemplate.objects.all()

    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        location    = request.POST.get('location', '').strip()
        status      = request.POST.get('status', 'draft')
        start_date  = request.POST.get('start_date') or None
        end_date    = request.POST.get('end_date') or None
        template_id = request.POST.get('template_id') or None

        if not name:
            messages.error(request, 'El nombre del evento es obligatorio.')
            return render(request, 'events/event_form.html', {'templates': templates})

        # Obtener plantilla si se eligió una
        template = None
        if template_id:
            template = EventTemplate.objects.filter(pk=template_id).first()

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
            from events.services.template_service import apply_template_to_event
            apply_template_to_event(event, template)
        else:
            # Sin plantilla: activar todos los módulos del MVP por defecto
            for module_type in ['tasks', 'attendees', 'checklist', 'files']:
                EventModule.objects.get_or_create(event=event, module_type=module_type)

        messages.success(request, f'Evento "{event.name}" creado exitosamente.')
        return redirect('events:event_detail', pk=event.pk)

    return render(request, 'events/event_form.html', {'templates': templates})


# ─────────────────────────────────────────────
#  EDITAR EVENTO
# ─────────────────────────────────────────────

@login_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == 'POST':
        event.name        = request.POST.get('name', event.name).strip()
        event.description = request.POST.get('description', '').strip()
        event.location    = request.POST.get('location', '').strip()
        event.status      = request.POST.get('status', event.status)
        event.start_date  = request.POST.get('start_date') or None
        event.end_date    = request.POST.get('end_date') or None
        event.save()

        messages.success(request, f'Evento "{event.name}" actualizado.')
        return redirect('events:event_detail', pk=event.pk)

    return render(request, 'events/event_form.html', {
        'event':     event,
        'templates': EventTemplate.objects.all(),
    })


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
    # Filtro por categoría
    category = request.GET.get('category', '')
    templates = EventTemplate.objects.all()
    if category:
        templates = templates.filter(category=category)

    context = {
        'templates':         templates,
        'category_filter':   category,
        'category_choices':  EventTemplate.CATEGORY_CHOICES,
    }
    return render(request, 'events/template_list.html', context)
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
 
    # Todos los eventos del usuario (sin rango, el JS filtra)
    all_events = Event.objects.filter(
        owner=request.user
    ).select_related('template').order_by('start_date')
 
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
 