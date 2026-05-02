from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from types import SimpleNamespace
import csv

from events.models import Event
from .models import Task, Attendee, Checklist, ChecklistItem, File, Budget, BudgetItem
from .forms import TaskForm, AttendeeForm, ChecklistForm, FileForm



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

    # Sugerencias de orden de prioridad (solo tareas pendientes/en progreso)
    from events.engine.prioritizer import prioritize_tasks
    try:
        pending_qs = event.tasks.filter(status__in=['pending', 'in_progress'])
        priority_suggestions = prioritize_tasks(pending_qs)
    except Exception:
        priority_suggestions = []

    from django.utils import timezone as tz
    context = {
        'event':               event,
        'tasks':               tasks,
        'status_filter':       status_filter,
        'status_choices':      Task.STATUS_CHOICES,
        'priority_suggestions': priority_suggestions,
        'today':               tz.now().date(),
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

    # Conexión tarea ↔ presupuesto
    try:
        event_budget = Budget.objects.get(event=event)
        task_budget_items = task.budget_items.select_related('budget').all()
        has_budget = True
    except Budget.DoesNotExist:
        event_budget = None
        task_budget_items = []
        has_budget = False

    context = {
        'event': event,
        'task': task,
        'form': form,
        'object': task,
        'event_budget': event_budget,
        'task_budget_items': task_budget_items,
        'has_budget': has_budget,
    }
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
        'cancel_url': reverse('modules:task_list', kwargs={'event_pk': event.pk}),
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
        'cancel_url': reverse('modules:attendee_list', kwargs={'event_pk': event.pk}),
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
        'event': checklist.event,
        'cancel_url': reverse('modules:checklist_list', kwargs={'event_pk': event_pk}),
    })


# ─────────────────────────────────────────────
#  ARCHIVOS
# ─────────────────────────────────────────────

_EXT_TYPE = {
    'pdf': 'pdf',
    'doc': 'document', 'docx': 'document', 'odt': 'document', 'txt': 'document',
    'xls': 'spreadsheet', 'xlsx': 'spreadsheet', 'csv': 'spreadsheet', 'ods': 'spreadsheet',
    'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image',
    'webp': 'image', 'svg': 'image', 'bmp': 'image',
}


def _detect_file_meta(uploaded_file):
    """Devuelve (name_sugerido, file_type, page_count_o_None)."""
    import os
    original = uploaded_file.name or ''
    stem, ext = os.path.splitext(original)
    ext = ext.lstrip('.').lower()
    file_type = _EXT_TYPE.get(ext, 'other')
    name = stem.replace('_', ' ').replace('-', ' ').strip() or original

    pages = None
    try:
        if ext == 'pdf':
            from PyPDF2 import PdfReader
            reader = PdfReader(uploaded_file)
            pages = len(reader.pages)
            uploaded_file.seek(0)
        elif ext == 'docx':
            from docx import Document
            doc = Document(uploaded_file)
            pages = len(doc.paragraphs)   # approx: párrafos como proxy
            uploaded_file.seek(0)
    except Exception:
        pass

    return name, file_type, pages


@login_required
def file_list(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    files = event.files.all().order_by('-uploaded_at')
    return render(request, 'modules/file_list.html', {'event': event, 'files': files})


@login_required
def file_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)

    if request.method == 'POST':
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.event = event
            file_obj.uploaded_by = request.user

            # Auto-detectar nombre y tipo si el usuario los dejó en blanco/default
            uploaded = request.FILES.get('file')
            if uploaded:
                auto_name, auto_type, _ = _detect_file_meta(uploaded)
                if not file_obj.name or file_obj.name == uploaded.name:
                    file_obj.name = auto_name
                if file_obj.file_type == 'other' and auto_type != 'other':
                    file_obj.file_type = auto_type

            file_obj.save()
            messages.success(request, f'Archivo "{file_obj.name}" subido correctamente.')
            return redirect('modules:file_list', event_pk=event.pk)
    else:
        form = FileForm()

    return render(request, 'modules/file_form.html', {'event': event, 'form': form})


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
        'cancel_url': reverse('modules:file_list', kwargs={'event_pk': event.pk}),
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
    # done → pending; cualquier otro estado → done
    task.status = 'pending' if task.status == 'done' else 'done'
    task.save()
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('modules:task_overview')


# ─────────────────────────────────────────────
#  PRESUPUESTO
# ─────────────────────────────────────────────

@login_required
def budget_detail(request, event_pk):
    """Muestra el presupuesto del evento, creándolo si no existe."""
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    budget, _ = Budget.objects.get_or_create(
        event=event,
        defaults={'total_budget': 0, 'currency': 'COP'},
    )
    items = budget.items.all().order_by('-created_at')
    expenses = items.filter(item_type='expense')
    incomes = items.filter(item_type='income')

    from django.db.models import Sum
    total_expenses = expenses.aggregate(t=Sum('amount'))['t'] or 0
    total_incomes = incomes.aggregate(t=Sum('amount'))['t'] or 0
    net_balance = total_incomes - total_expenses

    context = {
        'event': event,
        'budget': budget,
        'expenses': expenses,
        'incomes': incomes,
        'total_expenses': total_expenses,
        'total_incomes': total_incomes,
        'net_balance': net_balance,
        'total_spent': budget.total_spent,
        'remaining': budget.remaining,
        'usage_percentage': budget.usage_percentage,
        'category_choices': BudgetItem.CATEGORY_CHOICES,
        'type_choices': BudgetItem.TYPE_CHOICES,
        'event_tasks': event.tasks.exclude(status='done').order_by('title'),
    }
    return render(request, 'modules/budget_detail.html', context)


@login_required
def budget_update(request, event_pk):
    """Actualiza total_budget y currency del presupuesto."""
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    budget, _ = Budget.objects.get_or_create(event=event, defaults={'total_budget': 0})

    if request.method == 'POST':
        try:
            budget.total_budget = request.POST.get('total_budget', budget.total_budget)
            budget.currency = request.POST.get('currency', budget.currency).strip()[:3]
            budget.notes = request.POST.get('notes', '').strip()
            budget.save()
            messages.success(request, 'Presupuesto actualizado.')
        except Exception:
            messages.error(request, 'Error al actualizar el presupuesto.')

    return redirect('modules:budget_detail', event_pk=event.pk)


@login_required
def budget_item_create(request, event_pk):
    """Crea un BudgetItem para el presupuesto del evento.
    Acepta ?task=pk para preseleccionar related_task, y ?next=url para redirigir
    de vuelta a la página de edición de tarea después de crear el ítem.
    """
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    budget, _ = Budget.objects.get_or_create(event=event, defaults={'total_budget': 0})

    # Tarea prefill desde query param (viene de task_edit)
    prefill_task_pk = request.GET.get('task') or request.POST.get('from_task')
    prefill_task = None
    if prefill_task_pk:
        try:
            prefill_task = Task.objects.get(pk=prefill_task_pk, event=event)
        except Task.DoesNotExist:
            pass

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        amount_str = request.POST.get('amount', '0').strip()
        item_type = request.POST.get('item_type', 'expense')
        category = request.POST.get('category', 'other')
        paid = request.POST.get('paid') == 'on'
        due_date = request.POST.get('due_date') or None

        related_task_pk = request.POST.get('related_task') or request.POST.get('from_task')
        related_task = None
        if related_task_pk:
            try:
                related_task = Task.objects.get(pk=related_task_pk, event=event)
            except Task.DoesNotExist:
                pass

        if not name:
            messages.error(request, 'El nombre del ítem es obligatorio.')
        else:
            try:
                amount = float(amount_str)
                BudgetItem.objects.create(
                    budget=budget,
                    name=name,
                    amount=amount,
                    item_type=item_type,
                    category=category,
                    paid=paid,
                    due_date=due_date,
                    related_task=related_task,
                )
                messages.success(request, f'"{name}" agregado al presupuesto.')
            except ValueError:
                messages.error(request, 'El monto ingresado no es válido.')

        next_url = request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('modules:budget_detail', event_pk=event.pk)

    # GET: mostrar formulario con tarea prefill
    context = {
        'event': event,
        'budget': budget,
        'prefill_task': prefill_task,
        'event_tasks': event.tasks.exclude(status='done'),
        'category_choices': BudgetItem.CATEGORY_CHOICES,
        'type_choices': BudgetItem.TYPE_CHOICES,
    }
    return render(request, 'modules/budget_item_form.html', context)


@login_required
def budget_item_delete(request, event_pk, pk):
    """Elimina un BudgetItem."""
    event = get_object_or_404(Event, pk=event_pk, owner=request.user)
    item = get_object_or_404(BudgetItem, pk=pk, budget__event=event)

    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Ítem eliminado.')

    return redirect('modules:budget_detail', event_pk=event.pk)


@login_required
def export_tasks_csv(request):
    """Export all tasks for the logged-in user as CSV."""
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