from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from events.models import Event
from .models import Task, Attendee, Checklist, ChecklistItem, File
from types import SimpleNamespace
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseForbidden
import csv



# ─────────────────────────────────────────────
#  TAREAS
# ─────────────────────────────────────────────

@login_required
def task_list(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    tasks = event.tasks.all().order_by('-created_at')

    # Filtro por estado
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    context = {
        'event':         event,
        'tasks':         tasks,
        'status_filter': status_filter,
        'status_choices': Task.STATUS_CHOICES,
    }
    return render(request, 'modules/task_list.html', context)


@login_required
def task_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        priority    = request.POST.get('priority', 'medium')
        status      = request.POST.get('status', 'pending')
        due_date    = request.POST.get('due_date') or None

        if not title:
            messages.error(request, 'El título de la tarea es obligatorio.')
        else:
            Task.objects.create(
                event=event,
                title=title,
                description=description,
                priority=priority,
                status=status,
                due_date=due_date,
            )
            messages.success(request, f'Tarea "{title}" creada.')
            return redirect('modules:task_list', event_pk=event.pk)

    # Build a minimal `form` object so the template can read `.field.value` safely.
    empty = lambda v='': SimpleNamespace(value=v)
    form = SimpleNamespace(
        title=empty(''),
        description=empty(''),
        priority=empty('medium'),
        status=empty('pending'),
        due_date=empty('')
    )
    context = {'event': event, 'form': form, 'object': None}
    return render(request, 'modules/task_form.html', context)


@login_required
def task_edit(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    task  = get_object_or_404(Task, pk=pk, event=event)

    if request.method == 'POST':
        task.title       = request.POST.get('title', task.title).strip()
        task.description = request.POST.get('description', '').strip()
        task.priority    = request.POST.get('priority', task.priority)
        task.status      = request.POST.get('status', task.status)
        task.due_date    = request.POST.get('due_date') or None
        task.save()
        messages.success(request, 'Tarea actualizada.')
        return redirect('modules:task_list', event_pk=event.pk)

    # Provide a minimal `form` object matching what the template expects.
    def fv(v):
        # ensure date is ISO format for input value
        if hasattr(v, 'isoformat'):
            return SimpleNamespace(value=v.isoformat())
        return SimpleNamespace(value=v if v is not None else '')

    form = SimpleNamespace(
        title=fv(task.title),
        description=fv(task.description),
        priority=fv(task.priority),
        status=fv(task.status),
        due_date=fv(task.due_date),
    )

    context = {'event': event, 'task': task, 'form': form, 'object': task}
    return render(request, 'modules/task_form.html', context)


@login_required
def task_delete(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    task  = get_object_or_404(Task, pk=pk, event=event)

    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Tarea eliminada.')
        return redirect('modules:task_list', event_pk=event.pk)

    return render(request, 'modules/confirm_delete.html', {
        'object': task, 'object_name': task.title, 'event': event,
        'cancel_url': f'/modules/events/{event.pk}/tasks/',
    })


# ─────────────────────────────────────────────
#  ASISTENTES
# ─────────────────────────────────────────────

@login_required
def attendee_list(request, event_pk):
    event     = get_object_or_404(Event, pk=event_pk, owner=request.user)
    attendees = event.attendees.all().order_by('name')
    context   = {'event': event, 'attendees': attendees}
    return render(request, 'modules/attendee_list.html', context)


@login_required
def attendee_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)

    if request.method == 'POST':
        name   = request.POST.get('name', '').strip()
        email  = request.POST.get('email', '').strip()
        status = request.POST.get('status', 'pending')

        if not name:
            messages.error(request, 'El nombre del asistente es obligatorio.')
        else:
            Attendee.objects.create(event=event, name=name, email=email, status=status)
            messages.success(request, f'{name} agregado a la lista.')
            return redirect('modules:attendee_list', event_pk=event.pk)

    return render(request, 'modules/attendee_form.html', {'event': event})


@login_required
def attendee_edit(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    attendee = get_object_or_404(Attendee, pk=pk, event=event)

    if request.method == 'POST':
        attendee.name = request.POST.get('name', attendee.name).strip()
        attendee.email = request.POST.get('email', '').strip()
        attendee.status = request.POST.get('status', attendee.status)
        attendee.save()
        messages.success(request, 'Asistente actualizado.')
        return redirect('modules:attendee_list', event_pk=event.pk)

    return render(request, 'modules/attendee_form.html', {'event': event, 'attendee': attendee})


@login_required
def attendee_delete(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    attendee = get_object_or_404(Attendee, pk=pk, event=event)

    if request.method == 'POST':
        name = attendee.name
        attendee.delete()
        messages.success(request, f'{name} eliminado.')
        return redirect('modules:attendee_list', event_pk=event.pk)

    return render(request, 'modules/confirm_delete.html', {
        'object': attendee, 'object_name': attendee.name, 'event': event,
        'cancel_url': f'/modules/events/{event.pk}/attendees/',
    })


# ─────────────────────────────────────────────
#  CHECKLISTS
# ─────────────────────────────────────────────

@login_required
def checklist_list(request, event_pk):
    event      = get_object_or_404(Event, pk=event_pk, owner=request.user)
    checklists = event.checklists.prefetch_related('items').all()
    context    = {'event': event, 'checklists': checklists}
    return render(request, 'modules/checklist_list.html', context)


@login_required
def checklist_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'El título es obligatorio.')
        else:
            Checklist.objects.create(event=event, title=title)
            messages.success(request, f'Checklist "{title}" creada.')
            return redirect('modules:checklist_list', event_pk=event.pk)

    return render(request, 'modules/checklist_form.html', {'event': event})


@login_required
def checklist_item_create(request, pk):
    checklist = get_object_or_404(Checklist, pk=pk, event__owner=request.user)

    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            ChecklistItem.objects.create(checklist=checklist, text=text)
            messages.success(request, 'Ítem agregado.')
        return redirect('modules:checklist_list', event_pk=checklist.event.pk)

    return render(request, 'modules/checklist_item_form.html', {'checklist': checklist})


@login_required
def checklist_item_toggle(request, pk):
    """Marca/desmarca un ítem. Se llama con POST desde un formulario."""
    item = get_object_or_404(ChecklistItem, pk=pk, checklist__event__owner=request.user)
    if request.method == 'POST':
        item.is_checked = not item.is_checked
        item.save()
    return redirect('modules:checklist_list', event_pk=item.checklist.event.pk)


@login_required
def checklist_delete(request, pk):
    checklist = get_object_or_404(Checklist, pk=pk, event__owner=request.user)
    event_pk = checklist.event.pk

    if request.method == 'POST':
        title = checklist.title
        checklist.delete()
        messages.success(request, f'Checklist "{title}" eliminada.')
        return redirect('modules:checklist_list', event_pk=event_pk)

    return render(request, 'modules/confirm_delete.html', {
        'object': checklist, 'object_name': checklist.title,
        'event': checklist.event, 'cancel_url': f'/modules/events/{event_pk}/checklists/',
    })


# ─────────────────────────────────────────────
#  ARCHIVOS
# ─────────────────────────────────────────────

@login_required
def file_list(request, event_pk):
    event   = get_object_or_404(Event, pk=event_pk, owner=request.user)
    files   = event.files.all().order_by('-uploaded_at')
    context = {'event': event, 'files': files}
    return render(request, 'modules/file_list.html', context)


@login_required
def file_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)

    if request.method == 'POST':
        name      = request.POST.get('name', '').strip()
        file_path = request.POST.get('file_path', '').strip()
        file_type = request.POST.get('file_type', 'other')

        if not name or not file_path:
            messages.error(request, 'Nombre y ruta del archivo son obligatorios.')
        else:
            File.objects.create(
                event=event,
                name=name,
                file_path=file_path,
                file_type=file_type,
                uploaded_by=request.user,
            )
            messages.success(request, f'Archivo "{name}" registrado.')
            return redirect('modules:file_list', event_pk=event.pk)

    return render(request, 'modules/file_form.html', {'event': event})


@login_required
def file_delete(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    file = get_object_or_404(File, pk=pk, event=event)

    if request.method == 'POST':
        name = file.name
        file.delete()
        messages.success(request, f'Archivo "{name}" eliminado.')
        return redirect('modules:file_list', event_pk=event.pk)

    return render(request, 'modules/confirm_delete.html', {
        'object': file, 'object_name': file.name, 'event': event,
        'cancel_url': f'/modules/events/{event.pk}/files/',
    })


@login_required
def task_overview(request):
    """Global tasks overview across all events owned by the user."""
    user = request.user
    tasks = Task.objects.filter(event__owner=user).select_related('event').order_by('-created_at')

    context = {
        'tasks': tasks,
    }
    return render(request, 'modules/task_overview.html', context)


@login_required
def task_toggle_done(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('POST required')
    task = get_object_or_404(Task, pk=pk, event__owner=request.user)
    # Toggle between done and pending
    task.status = 'done' if task.status != 'done' else 'pending'
    task.save()
    return redirect(request.POST.get('next') or 'modules:task_overview')


@login_required
def export_tasks_csv(request):
    """Export all tasks for the logged-in user as CSV (MVP)."""
    user = request.user
    tasks = Task.objects.filter(event__owner=user).select_related('event')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tasks.csv"'

    writer = csv.writer(response)
    writer.writerow(['id', 'event', 'title', 'status', 'priority', 'assigned_to', 'due_date', 'created_at'])
    for t in tasks:
        writer.writerow([
            t.pk,
            t.event.name,
            t.title,
            t.status,
            t.priority,
            t.assigned_to.username if t.assigned_to else '',
            t.due_date.isoformat() if t.due_date else '',
            t.created_at.isoformat() if t.created_at else '',
        ])
    return response