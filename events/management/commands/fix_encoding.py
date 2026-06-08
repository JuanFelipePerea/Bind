from django.core.management.base import BaseCommand

from events.models import (
    Event, EventAlert, EventTemplate,
    Momento, TemplateBudgetItem, TemplateChecklistItem, TemplateTask,
)
from modules.models import Attendee, BudgetItem, Checklist, ChecklistItem, Task


def _fix(text):
    """Revierte doble-codificación UTF-8→Latin-1→UTF-8 (e.g. 'Ã±' → 'ñ')."""
    if not text or ('Ã' not in text and 'Â' not in text):
        return text
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _fix_qs(qs, fields, verbosity):
    count = 0
    for obj in qs.iterator():
        changed = False
        for field in fields:
            old = getattr(obj, field) or ''
            new = _fix(old)
            if new != old:
                setattr(obj, field, new)
                changed = True
        if changed:
            obj.save(update_fields=fields)
            count += 1
    if verbosity >= 1:
        print(f'  {qs.model.__name__}: {count} fila(s) corregida(s)')
    return count


class Command(BaseCommand):
    help = 'Corrige codificación UTF-8 mal interpretada como Latin-1 en toda la BD'

    def handle(self, *args, **options):
        v = options.get('verbosity', 1)
        total = 0
        for qs, fields in [
            (EventTemplate.objects.all(),        ['name', 'description']),
            (Event.objects.all(),                ['name', 'description', 'location']),
            (TemplateTask.objects.all(),         ['title', 'description']),
            (TemplateChecklistItem.objects.all(),['checklist_title', 'item_text']),
            (TemplateBudgetItem.objects.all(),   ['name']),
            (Momento.objects.all(),              ['titulo', 'descripcion']),
            (EventAlert.objects.all(),           ['title', 'message', 'action_label']),
            (Task.objects.all(),                 ['title', 'description']),
            (Attendee.objects.all(),             ['name']),
            (Checklist.objects.all(),            ['title']),
            (ChecklistItem.objects.all(),        ['text']),
            (BudgetItem.objects.all(),           ['name']),
        ]:
            total += _fix_qs(qs, fields, v)

        self.stdout.write(self.style.SUCCESS(f'\nTotal: {total} registro(s) corregido(s).'))
