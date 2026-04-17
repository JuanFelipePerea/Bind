"""
Stats — cálculo de estadísticas agregadas del usuario.

Centraliza compute_user_stats() que antes vivía en views.py,
siguiendo el principio de separación de responsabilidades.
"""

from django.utils import timezone
from django.db.models import Count
from datetime import timedelta

from .models import Event
from modules.models import Task, File, Checklist


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
    total_files = File.objects.filter(event__owner=user).count()

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

    all_checklists = Checklist.objects.filter(event__owner=user).prefetch_related('items')
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
