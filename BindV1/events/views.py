from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q

from .models import Event, EventTemplate, EventModule, TemplateModule
from modules.models import Task, File, Checklist
from datetime import timedelta


def compute_user_stats(user):
    """Compute report statistics for a given user. Returns a dict usable by report_view and dashboard."""
    today = timezone.now().date()
    events_qs = Event.objects.filter(owner=user)

    total_events = events_qs.count()
    active_events = events_qs.filter(status='active').count()
    completed_events = events_qs.filter(status='completed').count()
    cancelled_events = events_qs.filter(status='cancelled').count()

    tasks_qs = Task.objects.filter(event__owner=user)
    total_tasks = tasks_qs.count()
    done_tasks = tasks_qs.filter(status='done').count()
    pending_tasks = tasks_qs.filter(status='pending').count()
    inprog_tasks = tasks_qs.filter(status='in_progress').count()
    task_completion_rate = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    total_attendees = user.attendances.count() if hasattr(user, 'attendances') else 0
    confirmed_attendees = user.attendances.filter(status='confirmed').count() if hasattr(user, 'attendances') else 0
    total_files = File.objects.filter(event__owner=user).count() if 'File' in globals() else 0

    # weekly activity
    days_labels = []
    days_short = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    tasks_per_day = []
    max_tasks_day = 0
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = tasks_qs.filter(updated_at__date=day, status='done').count()
        label = days_short[day.weekday()]
        days_labels.append(label)
        tasks_per_day.append(count)
        if count > max_tasks_day:
            max_tasks_day = count
    if max_tasks_day > 0:
        tasks_per_day_pct = [max(int((c / max_tasks_day) * 100), 4) if c > 0 else 4 for c in tasks_per_day]
    else:
        tasks_per_day_pct = [4] * 7
    today_label = days_short[today.weekday()]
    weekly_activity = list(zip(days_labels, tasks_per_day, tasks_per_day_pct))

    high_tasks = tasks_qs.filter(priority='high').count()
    medium_tasks = tasks_qs.filter(priority='medium').count()
    low_tasks = tasks_qs.filter(priority='low').count()

    # events by category
    events_by_category = (
        events_qs
        .exclude(template__isnull=True)
        .values('template__category', 'template__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    upcoming = (
        events_qs
        .filter(status__in=['active', 'draft'], start_date__date__gte=today)
        .order_by('start_date')[:5]
    )
    # plain upcoming events with days_until for dashboard
    upcoming_events = []
    for ev in upcoming:
        if ev.start_date:
            delta = ev.start_date.date() - today
            ev.days_until = max(delta.days, 0)
        upcoming_events.append(ev)
    upcoming_with_data = []
    for ev in upcoming:
        t_total = ev.tasks.count()
        t_done = ev.tasks.filter(status='done').count()
        progress = int((t_done / t_total) * 100) if t_total > 0 else 0
        days_left = (ev.start_date.date() - today).days if ev.start_date else None
        upcoming_with_data.append({'event': ev, 'progress': progress, 'days_left': days_left, 't_total': t_total, 't_done': t_done})

    overdue_tasks = tasks_qs.filter(due_date__lt=today, status__in=['pending', 'in_progress']).select_related('event').order_by('due_date')[:10]

    all_checklists = Checklist.objects.filter(event__owner=user).prefetch_related('items') if 'Checklist' in globals() else []
    checklists_data = []
    for cl in all_checklists[:8]:
        total_items = cl.items.count()
        checked_items = cl.items.filter(is_checked=True).count()
        pct = int((checked_items / total_items) * 100) if total_items > 0 else 0
        checklists_data.append({'checklist': cl, 'total_items': total_items, 'checked_items': checked_items, 'progress': pct})

    # featured event: next active with date
    featured_event = (
        events_qs.filter(status='active', start_date__isnull=False).order_by('start_date').first()
    )
    if featured_event and featured_event.start_date:
        delta = featured_event.start_date.date() - today
        featured_event.days_until = max(delta.days, 0)
        total_t = featured_event.tasks.count()
        done_t = featured_event.tasks.filter(status='done').count() if total_t > 0 else 0
        featured_event.task_progress = int((done_t / total_t) * 100) if total_t > 0 else 0

    # urgent tasks
    urgent_tasks = Task.objects.filter(event__owner=user, priority='high', status='pending').select_related('event')[:3]

    # recent events
    recent_events = events_qs.order_by('-updated_at')[:6]

    # tasks today
    tasks_today = tasks_qs.filter(due_date=today).count()

    context = {
        'total_events': total_events,
        'active_events': active_events,
        'completed_events': completed_events,
        'cancelled_events': cancelled_events,
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'pending_tasks': pending_tasks,
        'inprog_tasks': inprog_tasks,
        'task_completion_rate': task_completion_rate,
        'total_attendees': total_attendees,
        'confirmed_attendees': confirmed_attendees,
        'total_files': total_files,
        'weekly_activity': weekly_activity,
        'today_label': today_label,
        'max_tasks_day': max_tasks_day,
        'high_tasks': high_tasks,
        'medium_tasks': medium_tasks,
        'low_tasks': low_tasks,
        'events_by_category': events_by_category,
        'upcoming_with_data': upcoming_with_data,
        'upcoming_events': upcoming_events,
        'overdue_tasks': overdue_tasks,
        'checklists_data': checklists_data,
        'featured_event': featured_event,
        'urgent_tasks': urgent_tasks,
        'recent_events': recent_events,
        'tasks_today': tasks_today,
        'today': today,
    }
    return context


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    stats = compute_user_stats(request.user)

    # Prepare dashboard-specific context (pick a subset)
    context = {
        'active_events_count': stats['active_events'],
        'total_events':        stats['total_events'],
        'pending_tasks':       stats['pending_tasks'],
        'tasks_today':         stats.get('tasks_today', 0),
        'featured_event':      stats.get('featured_event'),
        'upcoming_events':     stats.get('upcoming_events', [])[:5],
        'urgent_tasks':        stats.get('urgent_tasks')[:3] if stats.get('urgent_tasks') is not None else [],
        'recent_events':       stats.get('recent_events', [])[:6],
        # Add report-level stats for richer dashboard
        'weekly_activity':     stats.get('weekly_activity', []),
        'today_label':         stats.get('today_label', ''),
        'max_tasks_day':       stats.get('max_tasks_day', 0),
        'high_tasks':          stats.get('high_tasks', 0),
        'medium_tasks':        stats.get('medium_tasks', 0),
        'low_tasks':           stats.get('low_tasks', 0),
        'overdue_tasks':       stats.get('overdue_tasks', []),
    }
    return render(request, 'events/dashboard.html', context)


# ─────────────────────────────────────────────
#  LISTA DE EVENTOS
# ─────────────────────────────────────────────

@login_required
def event_list(request):
    events = Event.objects.filter(owner=request.user).order_by('-updated_at')

    # Filtro por status (desde query param ?status=active)
    status_filter = request.GET.get('status', '')
    if status_filter:
        events = events.filter(status=status_filter)

    # Búsqueda rápida ?q=nombre
    q = request.GET.get('q', '')
    if q:
        events = events.filter(name__icontains=q)

    context = {
        'events':        events,
        'status_filter': status_filter,
        'q':             q,
        'status_choices': Event.STATUS_CHOICES,
    }
    return render(request, 'events/event_list.html', context)


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

    context = {
        'event':          event,
        'active_modules': list(active_modules),
        'task_progress':  task_progress,
        'days_until':     days_until,
        'tasks':          event.tasks.all().order_by('-created_at')[:5],
        'attendees':      event.attendees.all()[:5],
        'checklists':     event.checklists.all()[:3],
        'files':          event.files.all()[:5],
    }
    return render(request, 'events/event_detail.html', context)


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

        # Activar módulos según la plantilla elegida (o todos por defecto)
        if template:
            for tm in template.modules.all():
                EventModule.objects.create(event=event, module_type=tm.module_type)
        else:
            # Sin plantilla: activar todos los módulos del MVP por defecto
            for module_type in ['tasks', 'attendees', 'checklist', 'files']:
                EventModule.objects.create(event=event, module_type=module_type)

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