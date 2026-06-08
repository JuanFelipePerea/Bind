import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q

from django.db import models as db_models
from django.conf import settings
from .models import Event, EventTemplate, EventModule, TemplateModule, EventAlert, EngineMetrics, Momento
from .stats import compute_user_stats
from modules.models import Task, File, Checklist, ChecklistItem
from datetime import timedelta
import calendar as cal_module
from datetime import date as date_cls

logger = logging.getLogger(__name__)


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

    bynix_opening_message = None
    try:
        from django.core.cache import cache as _djcache
        from events.services.ai_service import generate_dashboard_narrative
        _cache_key = f"bynix_narrative_{request.user.pk}"
        bynix_opening_message = _djcache.get(_cache_key)
        if not bynix_opening_message:
            _narrative = generate_dashboard_narrative(stats)
            bynix_opening_message = _narrative.get('narrative', '') or None
            if bynix_opening_message:
                _djcache.set(_cache_key, bynix_opening_message, timeout=3600)
    except Exception:
        pass

    # Eventos activos con presupuesto definido (para widget de salud presupuestaria)
    from modules.models import Budget
    budget_events = (
        Event.objects.filter(owner=request.user, status__in=['active', 'draft'])
        .select_related('budget')
        .filter(budget__isnull=False)
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

    show_tour = not getattr(getattr(request.user, 'profile', None), 'onboarding_completed', True)

    from events.models import EventCollaborator as _EC
    pending_invitations = list(
        _EC.objects.filter(user=request.user, accepted=False)
        .select_related('event', 'invited_by')
        .order_by('-invited_at')[:10]
    )
    shared_events = list(
        Event.objects.filter(collaborators__user=request.user, collaborators__accepted=True)
        .select_related('owner')
        .order_by('-updated_at')[:6]
    )

    context = {
        'active_events_count': stats['active_events'],
        'total_events':        stats['total_events'],
        'pending_tasks':       stats['pending_tasks'],
        'tasks_today':         stats.get('tasks_today', 0),
        'featured_event':      stats.get('featured_event'),
        'upcoming_events':     stats.get('upcoming_events', [])[:5],
        'urgent_tasks':        stats.get('urgent_tasks', [])[:3],
        'smart_tasks':         stats.get('smart_tasks', []),
        'critical_task':       stats.get('critical_task'),
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
        'budget_events':         budget_events,
        'show_tour':             show_tour,
        'pending_invitations':   pending_invitations,
        'shared_events':         shared_events,
        'bynix_opening_message': bynix_opening_message,
    }
    return render(request, 'events/dashboard.html', context)


@login_required
def email_health_check(request):
    """
    Diagnóstico de configuración SMTP. Solo superadmins o admins de BIND.
    GET  → muestra config (sin exponer la password completa)
    POST → intenta enviar un email de prueba al usuario autenticado
    """
    from accounts.views import is_bind_admin
    if not is_bind_admin(request.user):
        return JsonResponse({'error': 'Sin permiso'}, status=403)

    config = {
        'EMAIL_BACKEND':     settings.EMAIL_BACKEND,
        'EMAIL_HOST':        settings.EMAIL_HOST,
        'EMAIL_PORT':        settings.EMAIL_PORT,
        'EMAIL_USE_TLS':     settings.EMAIL_USE_TLS,
        'EMAIL_HOST_USER':   settings.EMAIL_HOST_USER,
        'EMAIL_HOST_PASSWORD_SET': bool(settings.EMAIL_HOST_PASSWORD),
        'DEFAULT_FROM_EMAIL': settings.DEFAULT_FROM_EMAIL,
        'SITE_URL':          settings.SITE_URL,
    }

    if request.method == 'POST':
        from django.core.mail import send_mail
        try:
            send_mail(
                subject='BIND — Test SMTP',
                message=f'Diagnóstico desde {settings.SITE_URL or "localhost"}. Config: {config}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )
            return JsonResponse({'ok': True, 'sent_to': request.user.email, 'config': config})
        except Exception as exc:
            return JsonResponse({'ok': False, 'error': str(exc), 'type': type(exc).__name__, 'config': config}, status=500)

    return JsonResponse(config)


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
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
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
        EngineMetrics.objects.get_or_create(
            decision_key=alert.alert_key,
            defaults={
                'decision_type': alert.alert_type,
                'event': alert.event,
                'user': request.user,
                'health_score_at_decision': health,
                'risk_level_at_decision': risk,
                'user_acted': True,
                'action_taken': 'followed_action',
            },
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

    shared_events = list(
        Event.objects.filter(
            collaborators__user=request.user,
            collaborators__accepted=True,
        )
        .select_related('owner')
        .order_by('-updated_at')
    )

    context = {
        'events':         page_obj,
        'page_obj':       page_obj,
        'status_filter':  status_filter,
        'q':              q,
        'status_choices': Event.STATUS_CHOICES,
        'shared_events':  shared_events,
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
    from django.http import Http404
    from events.models import EventCollaborator as _EC
    event = get_object_or_404(
        Event.objects.select_related('budget', 'template', 'owner'),
        pk=pk,
    )
    is_owner = event.owner == request.user
    if not is_owner:
        _collab = _EC.objects.filter(event=event, user=request.user, accepted=True).first()
        if not _collab:
            raise Http404
        user_role = _collab.role
    else:
        user_role = 'owner'
    collaborators = list(_EC.objects.filter(event=event).select_related('user', 'invited_by').order_by('invited_at'))

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

    engine_score = None
    engine_decisions_top = []
    try:
        from events.engine.context import build_event_context as build_engine_ctx
        from events.engine.scorer import score_event
        from events.engine.decisions import derive_decisions
        _ectx = build_engine_ctx(event)
        engine_score = score_event(_ectx)
        engine_decisions_top = derive_decisions(_ectx, engine_score)[:3]
    except Exception:
        pass

    # Saludo contextual de Bynix según la salud del evento
    bynix_greeting = None
    if engine_score is not None:
        hs = engine_score.health_score
        mo = engine_score.momentum_label
        name = event.name
        if hs < 40:
            top_msg = engine_decisions_top[0].message if engine_decisions_top else "hay alertas críticas pendientes"
            bynix_greeting = (
                f"Atención: el Engine marca «{name}» en estado crítico "
                f"(salud {hs}/100). {top_msg} ¿Revisamos juntos?"
            )
        elif hs < 60:
            bynix_greeting = (
                f"«{name}» está en zona de riesgo (salud {hs}/100, momentum: {mo}). "
                f"Hay puntos que necesitan atención. ¿Empezamos?"
            )
        elif mo in ('stalled', 'slowing'):
            bynix_greeting = (
                f"«{name}» tiene buena salud ({hs}/100) pero el momentum está {mo}. "
                f"¿Quieres que revisemos qué está frenando el avance?"
            )
        else:
            bynix_greeting = (
                f"«{name}» está en buen estado (salud {hs}/100). "
                f"¿Hay algo que quieras revisar antes del evento?"
            )

    context = {
        'event':               event,
        'is_owner':            is_owner,
        'user_role':           user_role,
        'can_edit':            is_owner or user_role == 'editor',
        'is_viewer':           user_role == 'viewer',
        'collaborators':       collaborators,
        'active_modules':      list(active_modules),
        'task_progress':       task_progress,
        'days_until':          days_until,
        'tasks_preview':       tasks_preview,
        'checklists_preview':  checklists_preview,
        'files_preview':       files_preview,
        'attendees_preview':   attendees_preview,
        'engine_score':           engine_score,
        'engine_decisions_top':   engine_decisions_top,
        'bynix_greeting':         bynix_greeting,
        'layout_config_json':     json.dumps(event.layout_config or {}, ensure_ascii=False),
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, 'events/event_detail.html', context)


# ─────────────────────────────────────────────
#  PERSISTENCIA DE LAYOUT (Gridstack)
# ─────────────────────────────────────────────

@login_required
def save_layout_config(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, pk=pk, owner=request.user)
    try:
        data = json.loads(request.body)
        layout = data.get('layout', {})
        if not isinstance(layout, dict):
            return JsonResponse({'error': 'Invalid layout'}, status=400)
        event.layout_config = layout
        event.save(update_fields=['layout_config'])
        return JsonResponse({'ok': True})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


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
                'templates':         templates,
                'templates_json':    _build_templates_json(templates),
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
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

        try:
            from accounts.services import push_event_to_google_calendar
            if hasattr(request.user, 'profile') and request.user.profile.google_calendar_connected:
                push_event_to_google_calendar(event, request.user)
        except Exception:
            pass  # El error de sync no debe impedir crear el evento

        return redirect('events:event_detail', pk=event.pk)

    selected_template = None
    template_param = request.GET.get('template')
    if template_param:
        selected_template = EventTemplate.objects.filter(pk=template_param).first()

    return render(request, 'events/event_form.html', {
        'templates':           templates,
        'templates_json':      _build_templates_json(templates),
        'selected_template':   selected_template,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
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
    # Solo el creador o staff pueden alterar la plantilla de forma permanente (fix IDOR)
    if request.POST.get('modify_template') == '1' and customization:
        if template.created_by != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Sin permiso para modificar esta plantilla'}, status=403)
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
        if 'invitation_file' in request.FILES:
            event.invitation_file = request.FILES['invitation_file']
        event.save()

        try:
            from accounts.services import push_event_to_google_calendar
            if hasattr(request.user, 'profile') and request.user.profile.google_calendar_connected:
                push_event_to_google_calendar(event, request.user)
        except Exception:
            pass  # El error de sync no debe impedir editar el evento

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
        'event':               event,
        'object':              event,
        'templates':           EventTemplate.objects.all(),
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
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
def template_create(request):
    active_modules = []
    form_data = {}
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        active_modules = request.POST.getlist('modules')
        form_data = {
            'name': name,
            'description': request.POST.get('description', ''),
            'category': request.POST.get('category', 'business'),
            'color': request.POST.get('color', '#3B82F6'),
        }
        if not name:
            messages.error(request, 'El nombre es obligatorio.')
        else:
            tmpl = EventTemplate.objects.create(
                created_by=request.user, **form_data
            )
            for mod in active_modules:
                TemplateModule.objects.get_or_create(template=tmpl, module_type=mod)
            messages.success(request, f'Plantilla "{tmpl.name}" creada.')
            return redirect('events:template_list')
    return render(request, 'events/template_form.html', {
        'category_choices': EventTemplate.CATEGORY_CHOICES,
        'module_choices': TemplateModule.MODULE_CHOICES,
        'active_modules': active_modules,
        'form_data': form_data,
    })


@login_required
def template_edit(request, template_id):
    tmpl = get_object_or_404(EventTemplate, pk=template_id)
    if tmpl.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'No tienes permiso para editar esta plantilla.')
        return redirect('events:template_list')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        active_modules = request.POST.getlist('modules')
        if not name:
            messages.error(request, 'El nombre es obligatorio.')
            return render(request, 'events/template_form.html', {
                'template': tmpl,
                'category_choices': EventTemplate.CATEGORY_CHOICES,
                'module_choices': TemplateModule.MODULE_CHOICES,
                'active_modules': active_modules,
                'form_data': {
                    'name': name,
                    'description': request.POST.get('description', ''),
                    'category': request.POST.get('category', tmpl.category),
                    'color': request.POST.get('color', tmpl.color),
                },
            })
        tmpl.name = name
        tmpl.description = request.POST.get('description', '').strip()
        tmpl.category = request.POST.get('category', tmpl.category)
        tmpl.color = request.POST.get('color', tmpl.color)
        tmpl.save()
        tmpl.modules.all().delete()
        for mod in set(active_modules):
            TemplateModule.objects.create(template=tmpl, module_type=mod)
        messages.success(request, f'Plantilla "{tmpl.name}" actualizada.')
        return redirect('events:template_list')
    return render(request, 'events/template_form.html', {
        'template': tmpl,
        'category_choices': EventTemplate.CATEGORY_CHOICES,
        'module_choices': TemplateModule.MODULE_CHOICES,
        'active_modules': list(tmpl.modules.values_list('module_type', flat=True)),
        'form_data': {
            'name': tmpl.name,
            'description': tmpl.description,
            'category': tmpl.category,
            'color': tmpl.color,
        },
    })


@login_required
def template_delete(request, template_id):
    template = get_object_or_404(EventTemplate, pk=template_id)
    if template.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'No tienes permiso para eliminar esta plantilla.')
        return redirect('events:template_list')
    if request.method == 'POST':
        name = template.name
        template.delete()
        messages.success(request, f'Plantilla "{name}" eliminada.')
        return redirect('events:template_list')
    return render(request, 'events/template_confirm_delete.html', {'template': template})


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

    # Tareas con fecha límite — se necesita event__template para el color
    all_tasks = Task.objects.filter(
        event__owner=request.user,
        due_date__isnull=False,
    ).select_related('event', 'event__template').order_by('due_date')

    # Próximos 5 eventos para el panel lateral
    upcoming_events = Event.objects.filter(
        owner=request.user,
        start_date__date__gte=today,
        status__in=['active', 'draft'],
    ).order_by('start_date')[:5]

    # ── SRV JSON ──────────────────────────────────────────────────────────────
    # Construimos el array en Python para garantizar tipos correctos y evitar
    # que la localización es-co (coma decimal) rompa el JavaScript en producción.
    from django.core.serializers.json import DjangoJSONEncoder

    from django.utils.timezone import localtime as _localtime

    srv_data = []

    for ev in all_events:
        _start = _localtime(ev.start_date) if ev.start_date else None
        _end   = _localtime(ev.end_date)   if ev.end_date   else None
        srv_data.append({
            'id':          ev.pk,
            'eventId':     ev.pk,
            'eventName':   ev.name,
            'eventColor':  ev.template.color if ev.template else '#14b8a6',
            'title':       ev.name,
            'status':      ev.status,
            'start':       _start.strftime('%Y-%m-%d') if _start else '',
            'startFull':   _start.strftime('%Y-%m-%dT%H:%M') if _start else '',
            'end':         (_end.strftime('%Y-%m-%d') if _end
                            else (_start.strftime('%Y-%m-%d') if _start else '')),
            'loc':         ev.location or '',
            'desc':        (ev.description or '')[:90],
            'viewUrl':     reverse('events:event_detail', args=[ev.pk]),
            'editUrl':     reverse('events:event_edit',   args=[ev.pk]),
            'delUrl':      reverse('events:event_delete', args=[ev.pk]),
            'type':        'event',
            'progress':    int(ev.task_progress_pct),
            'budgetPct':   int(ev.budget_pct),
            'budgetUsed':  round(float(ev.budget_used),  2),
            'budgetTotal': round(float(ev.budget_total), 2),
        })

    for t in all_tasks:
        srv_data.append({
            'id':         t.pk,
            'eventId':    t.event.pk,
            'eventName':  t.event.name,
            'eventColor': t.event.template.color if t.event.template else '#f59e0b',
            'title':      t.title,
            'status':     t.status,
            'start':      t.due_date.strftime('%Y-%m-%d') if t.due_date else '',
            'startFull':  (t.due_date.strftime('%Y-%m-%d') + 'T00:00') if t.due_date else '',
            'end':        t.due_date.strftime('%Y-%m-%d') if t.due_date else '',
            'loc':        '',
            'desc':       (t.description or '')[:90],
            'viewUrl':    reverse('modules:task_list',   args=[t.event.pk]),
            'editUrl':    reverse('modules:task_edit',   args=[t.event.pk, t.pk]),
            'delUrl':     reverse('modules:task_delete', args=[t.event.pk, t.pk]),
            'type':       'task',
            'priority':   t.priority,
        })

    # Momentos (hitos) de todos los eventos del usuario
    from django.utils.timezone import localtime as _localtime2
    all_momentos = Momento.objects.filter(
        evento__owner=request.user
    ).select_related('evento', 'evento__template').order_by('hora_inicio')

    for m in all_momentos:
        _mstart = _localtime2(m.hora_inicio)
        _mend   = _localtime2(m.hora_fin) if m.hora_fin else None
        _color  = m._TIPO_COLOR.get(m.tipo, '#6366F1')
        srv_data.append({
            'id':          m.pk,
            'eventId':     m.evento.pk,
            'eventName':   m.evento.name,
            'eventColor':  _color,
            'title':       m.titulo,
            'status':      m.tipo,
            'start':       _mstart.strftime('%Y-%m-%d'),
            'startFull':   _mstart.strftime('%Y-%m-%dT%H:%M'),
            'end':         (_mend.strftime('%Y-%m-%d') if _mend else _mstart.strftime('%Y-%m-%d')),
            'loc':         '',
            'desc':        (m.descripcion or '')[:90],
            'viewUrl':     reverse('events:event_detail', args=[m.evento.pk]),
            'editUrl':     reverse('events:momento_edit', args=[m.evento.pk, m.pk]),
            'delUrl':      reverse('events:momento_delete', args=[m.evento.pk, m.pk]),
            'type':        'momento',
            'importancia': m.importancia,
        })

    context = {
        'upcoming_events':     upcoming_events,
        'status_choices':      Event.STATUS_CHOICES,
        'today':               today,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'srv_data':            srv_data,  # lista Python — json_script serializa en template
    }
    return render(request, 'events/calendar.html', context)


# Vistas de Bynix movidas a events/views_bynix.py

# ─────────────────────────────────────────────
#  EVENTS API — Creación rápida vía IA
# ─────────────────────────────────────────────

@login_required
def event_api_create(request):
    """
    Crea un evento mínimo desde el Dashboard Bynix vía AJAX.
    Acepta JSON {name, description, start_date (YYYY-MM-DD opcional)}.
    Retorna {id, url} para que el JS redirija al nuevo evento.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)
        name = body.get('name', '').strip()[:200]
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Formato inválido'}, status=400)

    if not name:
        return JsonResponse({'error': 'El nombre del evento es obligatorio'}, status=400)

    from django.utils.dateparse import parse_date
    start_date = None
    raw_date = body.get('start_date')
    if raw_date:
        start_date = parse_date(str(raw_date))

    event = Event.objects.create(
        owner=request.user,
        name=name,
        description=body.get('description', '')[:2000],
        start_date=start_date,
        status='draft',
    )

    return JsonResponse({
        'id': event.pk,
        'url': reverse('events:event_detail', kwargs={'pk': event.pk}),
        'name': event.name,
    })


# ── Momentos ─────────────────────────────────────────────────────────────────

def _parse_momento_post(post, evento):
    """
    Extrae y valida los campos de Momento desde request.POST.
    Valida que hora_inicio/hora_fin estén dentro del rango start_date↔end_date del evento
    (solo cuando el evento tiene fechas definidas). Devuelve (datos, errores).
    """
    from django.utils.dateparse import parse_datetime

    errores = {}
    titulo = post.get('titulo', '').strip()
    if not titulo:
        errores['titulo'] = 'El título es obligatorio.'

    hora_inicio_raw = post.get('hora_inicio', '').strip()
    hora_fin_raw    = post.get('hora_fin', '').strip()

    hora_inicio = None
    hora_fin    = None

    if hora_inicio_raw:
        hora_inicio = parse_datetime(hora_inicio_raw)
        if hora_inicio is None:
            errores['hora_inicio'] = 'Formato de fecha inválido.'
        elif timezone.is_naive(hora_inicio):
            hora_inicio = timezone.make_aware(hora_inicio)
    else:
        errores['hora_inicio'] = 'La hora de inicio es obligatoria.'

    if hora_fin_raw:
        hora_fin = parse_datetime(hora_fin_raw)
        if hora_fin is None:
            errores['hora_fin'] = 'Formato de fecha inválido.'
        else:
            if timezone.is_naive(hora_fin):
                hora_fin = timezone.make_aware(hora_fin)
        if hora_fin and hora_inicio and hora_fin <= hora_inicio:
            errores['hora_fin'] = 'La hora de fin debe ser posterior a la hora de inicio.'

    # Validación de rango: el momento debe caer dentro de las fechas del evento.
    # Solo se aplica cuando el evento tiene fechas definidas; si no las tiene, se omite.
    if hora_inicio and not errores.get('hora_inicio'):
        if evento.start_date and hora_inicio < evento.start_date:
            errores['hora_inicio'] = (
                f'El momento no puede ser anterior al inicio del evento '
                f'({evento.start_date.strftime("%d/%m/%Y %H:%M")}).'
            )
        if evento.end_date and hora_inicio > evento.end_date:
            errores['hora_inicio'] = (
                f'El momento no puede ser posterior al fin del evento '
                f'({evento.end_date.strftime("%d/%m/%Y %H:%M")}).'
            )

    if hora_fin and not errores.get('hora_fin'):
        if evento.end_date and hora_fin > evento.end_date:
            errores['hora_fin'] = (
                f'La hora de fin no puede superar el fin del evento '
                f'({evento.end_date.strftime("%d/%m/%Y %H:%M")}).'
            )

    tipo        = post.get('tipo', 'protocolo')
    importancia = post.get('importancia', 'media')

    datos = {
        'titulo':      titulo,
        'descripcion': post.get('descripcion', '').strip(),
        'hora_inicio': hora_inicio,
        'hora_fin':    hora_fin,
        'tipo':        tipo,
        'importancia': importancia,
    }
    return datos, errores


@login_required
def momento_create(request, event_pk):
    evento = get_object_or_404(Event, pk=event_pk, owner=request.user)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        datos, errores = _parse_momento_post(request.POST, evento)

        if errores:
            if is_ajax:
                return JsonResponse({'ok': False, 'errores': errores}, status=400)
            messages.error(request, 'Por favor corrige los errores del formulario.')
        else:
            momento = Momento.objects.create(evento=evento, **datos)
            if is_ajax:
                return JsonResponse({'ok': True, 'momento': momento.to_dict()}, status=201)
            messages.success(request, f'Momento "{momento.titulo}" creado.')
            return redirect('events:event_detail', pk=event_pk)

    # GET — renderiza formulario
    context = {
        'evento':      evento,
        'accion':      'Crear',
        'tipo_choices': Momento.TIPO_CHOICES,
        'importancia_choices': Momento.IMPORTANCIA_CHOICES,
        'momento':     None,
    }
    return render(request, 'events/momento_form.html', context)


@login_required
def momento_edit(request, event_pk, pk):
    evento  = get_object_or_404(Event, pk=event_pk, owner=request.user)
    momento = get_object_or_404(Momento, pk=pk, evento=evento)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        datos, errores = _parse_momento_post(request.POST, evento)

        if errores:
            if is_ajax:
                return JsonResponse({'ok': False, 'errores': errores}, status=400)
            messages.error(request, 'Por favor corrige los errores del formulario.')
        else:
            for campo, valor in datos.items():
                setattr(momento, campo, valor)
            momento.save()
            if is_ajax:
                return JsonResponse({'ok': True, 'momento': momento.to_dict()})
            messages.success(request, f'Momento "{momento.titulo}" actualizado.')
            return redirect('events:event_detail', pk=event_pk)

    context = {
        'evento':      evento,
        'accion':      'Editar',
        'tipo_choices': Momento.TIPO_CHOICES,
        'importancia_choices': Momento.IMPORTANCIA_CHOICES,
        'momento':     momento,
    }
    return render(request, 'events/momento_form.html', context)


@login_required
def momento_delete(request, event_pk, pk):
    evento  = get_object_or_404(Event, pk=event_pk, owner=request.user)
    momento = get_object_or_404(Momento, pk=pk, evento=evento)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        titulo = momento.titulo
        momento.delete()
        if is_ajax:
            return JsonResponse({'ok': True, 'mensaje': f'Momento "{titulo}" eliminado.'})
        messages.success(request, f'Momento "{titulo}" eliminado.')
        return redirect('events:event_detail', pk=event_pk)

    if is_ajax:
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)
    return redirect('events:event_detail', pk=event_pk)


@login_required
def event_close(request, pk):
    """
    GET  → página de confirmación antes de cerrar.
    POST → marca el evento como 'completed' y redirige al dashboard.
    """
    event = get_object_or_404(Event, pk=pk, owner=request.user)
    if request.method == 'POST':
        event.status = 'completed'
        event.save()
        messages.success(request, f'Proyecto "{event.name}" cerrado correctamente.')
        return redirect('events:dashboard')
    return render(request, 'events/event_confirm_close.html', {'event': event})


@login_required
def event_set_status(request, pk):
    """Cambia el status de un evento vía POST {status}. Usado por el kebab menu."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    event = get_object_or_404(Event, pk=pk, owner=request.user)
    new_status = request.POST.get('status', '')
    valid = [s[0] for s in Event.STATUS_CHOICES]
    if new_status not in valid:
        return JsonResponse({'error': 'Estado inválido'}, status=400)

    previous_status = event.status
    event.status = new_status
    event.save(update_fields=['status', 'updated_at'])

    if previous_status != 'completed' and new_status == 'completed':
        _handle_event_completion(event, request.user)
        messages.success(request, f'"{event.name}" marcado como completado.')
    else:
        messages.success(request, f'Estado de "{event.name}" actualizado a {event.get_status_display()}.')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'status': new_status, 'label': event.get_status_display()})

    next_val = request.POST.get('next', '')
    if next_val and next_val.startswith('/') and not next_val.startswith('//'):
        return redirect(next_val)
    return redirect('events:event_detail', pk=pk)


@login_required
def tasks_complete_all(request, pk):
    """POST → marca todas las tareas pendientes/en progreso del evento como 'done'."""
    from modules.models import Task
    event = get_object_or_404(Event, pk=pk, owner=request.user)
    if request.method != 'POST':
        return redirect('events:event_detail', pk=pk)
    updated = Task.objects.filter(
        event=event, status__in=['pending', 'in_progress']
    ).update(status='done')
    messages.success(request, f'{updated} tarea{"s" if updated != 1 else ""} marcada{"s" if updated != 1 else ""} como completada{"s" if updated != 1 else ""}.')
    return redirect('events:event_detail', pk=pk)


@login_required
def momentos_json(request, event_pk):
    """
    Feed de Momentos de un evento.
    ?format=fullcalendar  → formato FullCalendar (default)
    ?format=list          → formato to_dict() para uso general
    """
    evento   = get_object_or_404(Event, pk=event_pk, owner=request.user)
    momentos = evento.momentos.all()
    fmt = request.GET.get('format', 'fullcalendar')
    if fmt == 'list':
        return JsonResponse([m.to_dict() for m in momentos], safe=False)
    return JsonResponse([m.to_fullcalendar_json() for m in momentos], safe=False)
