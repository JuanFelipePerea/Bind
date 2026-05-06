"""
Management command: test_template_automation

Valida que el sistema de plantillas de cero fricciones funcione correctamente:
  1. Selecciona la primera plantilla disponible
  2. Genera un evento con defaults inteligentes (sin start_date manual)
  3. Verifica que se crearon todas las tareas predefinidas
  4. Verifica que las tareas de alta prioridad se auto-asignaron al owner
  5. Verifica que las fechas se calcularon correctamente
  6. Verifica los checklists y el presupuesto
  7. Limpia los datos de prueba

Uso: python manage.py test_template_automation
     python manage.py test_template_automation --keep   (conserva evento de prueba)
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone


class Command(BaseCommand):
    help = 'Valida la automatizacion total del sistema de plantillas (zero friction).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep', action='store_true',
            help='No eliminar el evento de prueba al finalizar'
        )

    def handle(self, *args, **options):
        from events.models import EventTemplate, Event
        from events.services.template_service import (
            apply_template_to_event,
            get_smart_start_date,
            get_smart_end_date,
        )

        SEP = '-' * 60
        self.stdout.write('\n' + SEP)
        self.stdout.write('  TEST: Automatizacion Total de Plantillas')
        self.stdout.write(SEP)

        # 1. Obtener plantilla y usuario de prueba
        template = EventTemplate.objects.prefetch_related(
            'modules', 'default_tasks', 'default_checklist_items'
        ).first()

        if not template:
            self.stdout.write(self.style.ERROR(
                'No hay plantillas en la DB. Ejecuta: python manage.py seed_templates'
            ))
            return

        owner = User.objects.filter(is_active=True).first()
        if not owner:
            self.stdout.write(self.style.ERROR('No hay usuarios en la DB.'))
            return

        self.stdout.write(f'\n  Plantilla : {template.name} ({template.category})')
        self.stdout.write(f'  Owner     : {owner.username}')

        # 2. Calcular defaults inteligentes
        start_date = get_smart_start_date(template.category)
        end_date   = get_smart_end_date(start_date, template.category)

        self.stdout.write(f'\n  Start date auto: {start_date.strftime("%Y-%m-%d %H:%M")}')
        self.stdout.write(f'  End date auto  : {end_date.strftime("%Y-%m-%d %H:%M")}')

        # 3. Crear evento de prueba
        event_name = f'[TEST] {template.name} {timezone.now().strftime("%d/%m/%Y %H:%M")}'
        event = Event.objects.create(
            name=event_name,
            description=template.description,
            status='active',
            start_date=start_date,
            end_date=end_date,
            owner=owner,
            template=template,
        )
        self.stdout.write(f'\n  Evento creado: pk={event.pk}')

        # 4. Aplicar plantilla
        apply_template_to_event(event, template, owner=owner)

        # 5. Verificaciones
        errors = []
        ok   = self.style.SUCCESS('[OK]  ')
        fail = self.style.ERROR('[FAIL]')

        self.stdout.write('\n  Verificaciones:')

        # 5a. Tareas creadas
        tasks = list(event.tasks.all())
        expected_count = template.default_tasks.count()
        if len(tasks) == expected_count:
            self.stdout.write(f'  {ok} Tareas creadas: {len(tasks)}/{expected_count}')
        else:
            msg = f'Tareas creadas ({len(tasks)}) != esperadas ({expected_count})'
            errors.append(msg)
            self.stdout.write(f'  {fail} {msg}')

        # 5b. Tareas de alta prioridad auto-asignadas al owner
        high_tasks    = [t for t in tasks if t.priority == 'high']
        assigned_high = [t for t in high_tasks if t.assigned_to_id == owner.pk]
        if high_tasks and len(assigned_high) == len(high_tasks):
            self.stdout.write(
                f'  {ok} Auto-asignacion: {len(assigned_high)}/{len(high_tasks)} '
                f'tareas criticas asignadas a {owner.username}'
            )
        elif not high_tasks:
            self.stdout.write(f'  {ok} Sin tareas de alta prioridad en esta plantilla')
        else:
            msg = f'Auto-asignacion incompleta: {len(assigned_high)}/{len(high_tasks)}'
            errors.append(msg)
            self.stdout.write(f'  {fail} {msg}')

        # 5c. Fechas calculadas en tareas con days_before_event
        dated_template_tasks = template.default_tasks.exclude(days_before_event=None)
        tasks_with_dates     = [t for t in tasks if t.due_date is not None]
        if len(tasks_with_dates) == dated_template_tasks.count():
            self.stdout.write(f'  {ok} Fechas calculadas: {len(tasks_with_dates)} tareas con due_date')
        else:
            msg = f'Fechas calculadas ({len(tasks_with_dates)}) != esperadas ({dated_template_tasks.count()})'
            errors.append(msg)
            self.stdout.write(f'  {fail} {msg}')

        # 5d. Checklists creados
        checklists      = list(event.checklists.all())
        checklist_titles = {item.checklist_title for item in template.default_checklist_items.all()}
        if len(checklists) == len(checklist_titles):
            self.stdout.write(f'  {ok} Checklists creados: {len(checklists)}')
        else:
            msg = f'Checklists creados ({len(checklists)}) != esperados ({len(checklist_titles)})'
            errors.append(msg)
            self.stdout.write(f'  {fail} {msg}')

        # 5e. Presupuesto creado
        try:
            budget = event.budget
            self.stdout.write(f'  {ok} Presupuesto creado (currency={budget.currency})')
        except Exception:
            errors.append('Presupuesto no creado')
            self.stdout.write(f'  {fail} Presupuesto no creado')

        # 5f. Modulos activados
        active_modules   = list(event.modules.values_list('module_type', flat=True))
        template_modules = list(template.modules.values_list('module_type', flat=True))
        if set(active_modules) == set(template_modules):
            self.stdout.write(f'  {ok} Modulos activados: {", ".join(sorted(active_modules))}')
        else:
            msg = f'Modulos activados ({sorted(active_modules)}) != esperados ({sorted(template_modules)})'
            errors.append(msg)
            self.stdout.write(f'  {fail} {msg}')

        # 5g. Idempotencia: segunda llamada no duplica tareas
        apply_template_to_event(event, template, owner=owner)
        tasks_after = event.tasks.count()
        if tasks_after == expected_count:
            self.stdout.write(f'  {ok} Idempotencia: segunda aplicacion no duplico tareas')
        else:
            msg = f'Idempotencia rota: {tasks_after} tareas tras segunda llamada'
            errors.append(msg)
            self.stdout.write(f'  {fail} {msg}')

        # 6. Resumen de tareas en orden cronologico
        self.stdout.write('\n  Tareas generadas (orden cronologico):')
        for task in sorted(tasks, key=lambda t: t.due_date or timezone.now().date()):
            assigned  = f'-> {task.assigned_to.username}' if task.assigned_to else '-> sin asignar'
            due_str   = task.due_date.strftime('%Y-%m-%d') if task.due_date else 'sin fecha  '
            prio_lbl  = {'high': '[H]', 'medium': '[M]', 'low': '[L]'}.get(task.priority, '[-]')
            self.stdout.write(f'    {prio_lbl} [{due_str}] {task.title[:42]:<42} {assigned}')

        # 7. Limpieza
        if not options['keep']:
            event.delete()
            self.stdout.write('\n  Evento de prueba eliminado.')
        else:
            self.stdout.write(f'\n  Evento de prueba conservado (pk={event.pk}).')

        # 8. Resultado final
        self.stdout.write('\n' + SEP)
        if errors:
            self.stdout.write(self.style.ERROR(f'  FALLIDO -- {len(errors)} error(es):'))
            for e in errors:
                self.stdout.write(self.style.ERROR(f'    - {e}'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'  PASADO -- Plantilla "{template.name}" desplegada correctamente.\n'
                f'  {expected_count} tareas | fechas calculadas | asignacion automatica | idempotencia OK'
            ))
        self.stdout.write(SEP + '\n')
