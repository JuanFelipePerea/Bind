"""
Management command: seed_demo

Crea 3 eventos de demostración con datos realistas usando las plantillas base.
Requiere que seed_templates haya sido ejecutado primero.

Uso: python manage.py seed_demo --user=<username>
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Crea eventos de demostración con datos realistas para un usuario.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            required=True,
            help='Username del usuario para quien se crean los eventos.',
        )

    def handle(self, *args, **options):
        username = options['user']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"Usuario '{username}' no encontrado.")

        # Asegurar que las plantillas existen
        from events.models import EventTemplate
        if EventTemplate.objects.count() == 0:
            self.stdout.write('No hay plantillas. Ejecutando seed_templates...')
            from django.core.management import call_command
            call_command('seed_templates')

        from events.models import Event, EventTemplate
        from modules.models import Task, Attendee, Budget, BudgetItem
        from events.services.template_service import apply_template_to_event

        today = timezone.now().date()
        created_summary = {
            'events': 0, 'tasks_done': 0, 'attendees': 0, 'budget_items': 0,
        }

        # ── EVENTO 1: Conferencia Tech BIND 2025 ─────────────────────────────
        template_conf = EventTemplate.objects.filter(name='Conferencia Corporativa').first()
        event1, e1_created = Event.objects.get_or_create(
            name='Conferencia Tech BIND 2025',
            owner=user,
            defaults={
                'status': 'active',
                'start_date': timezone.make_aware(
                    timezone.datetime.combine(today + timedelta(days=18), timezone.datetime.min.time())
                ),
                'location': 'Centro de Convenciones, Cali',
                'template': template_conf,
                'description': 'Conferencia anual de tecnología organizada por el equipo BIND.',
            },
        )
        if e1_created:
            created_summary['events'] += 1
            if template_conf:
                apply_template_to_event(event1, template_conf)

        # Agregar 12 asistentes (mix de estados)
        attendees_data_1 = [
            ('Ana García', 'ana@ejemplo.com', 'confirmed'),
            ('Carlos López', 'carlos@ejemplo.com', 'confirmed'),
            ('María Rodríguez', 'maria@ejemplo.com', 'confirmed'),
            ('José Martínez', 'jose@ejemplo.com', 'confirmed'),
            ('Laura Sánchez', 'laura@ejemplo.com', 'confirmed'),
            ('Pedro Gómez', 'pedro@ejemplo.com', 'pending'),
            ('Isabel Díaz', 'isabel@ejemplo.com', 'pending'),
            ('Miguel Fernández', 'miguel@ejemplo.com', 'pending'),
            ('Sofía Torres', 'sofia@ejemplo.com', 'pending'),
            ('Andrés Ruiz', 'andres@ejemplo.com', 'declined'),
            ('Carmen Moreno', 'carmen@ejemplo.com', 'confirmed'),
            ('David Jiménez', 'david@ejemplo.com', 'pending'),
        ]
        for name, email, status in attendees_data_1:
            att, att_created = Attendee.objects.get_or_create(
                event=event1, email=email,
                defaults={'name': name, 'status': status},
            )
            if att_created:
                created_summary['attendees'] += 1

        # Crear presupuesto y actualizar total
        budget1, _ = Budget.objects.get_or_create(
            event=event1,
            defaults={'total_budget': 5000000, 'currency': 'COP'},
        )
        if budget1.total_budget == 0:
            budget1.total_budget = 5000000
            budget1.save()

        budget_items_1 = [
            ('Alquiler del salón principal', 1800000, 'expense', 'venue', True),
            ('Catering para 50 personas', 1200000, 'expense', 'catering', False),
            ('Equipos audiovisuales', 600000, 'expense', 'technology', True),
            ('Diseño y material de marketing', 400000, 'expense', 'marketing', False),
        ]
        for name, amount, itype, cat, paid in budget_items_1:
            _, bi_created = BudgetItem.objects.get_or_create(
                budget=budget1, name=name,
                defaults={'amount': amount, 'item_type': itype, 'category': cat, 'paid': paid},
            )
            if bi_created:
                created_summary['budget_items'] += 1

        # Marcar 4 tareas como done
        tasks_e1 = event1.tasks.filter(status='pending').order_by('due_date')[:4]
        for task in tasks_e1:
            task.status = 'done'
            task.save()
            created_summary['tasks_done'] += 1

        self.stdout.write(f"  [OK]Evento 1: {event1.name}")

        # ── EVENTO 2: Lanzamiento Producto Alpha ─────────────────────────────
        template_launch = EventTemplate.objects.filter(name='Lanzamiento de Producto').first()
        event2, e2_created = Event.objects.get_or_create(
            name='Lanzamiento Producto Alpha',
            owner=user,
            defaults={
                'status': 'draft',
                'start_date': timezone.make_aware(
                    timezone.datetime.combine(today + timedelta(days=45), timezone.datetime.min.time())
                ),
                'template': template_launch,
                'description': 'Lanzamiento oficial del Producto Alpha al mercado colombiano.',
            },
        )
        if e2_created:
            created_summary['events'] += 1
            if template_launch:
                apply_template_to_event(event2, template_launch)

        # Agregar 8 asistentes (todos pending)
        attendees_data_2 = [
            ('Roberto Silva', 'roberto@prensa.com', 'pending'),
            ('Patricia Vega', 'patricia@ventas.com', 'pending'),
            ('Hernando Cruz', 'hernando@stakeholder.com', 'pending'),
            ('Claudia Mendez', 'claudia@media.com', 'pending'),
            ('Felipe Castro', 'felipe@inversor.com', 'pending'),
            ('Natalia Ríos', 'natalia@prensa.com', 'pending'),
            ('Mauricio Parra', 'mauricio@socio.com', 'pending'),
            ('Alejandra Mora', 'alejandra@cliente.com', 'pending'),
        ]
        for name, email, status in attendees_data_2:
            att, att_created = Attendee.objects.get_or_create(
                event=event2, email=email,
                defaults={'name': name, 'status': status},
            )
            if att_created:
                created_summary['attendees'] += 1

        # Marcar 1 tarea como done
        task_e2 = event2.tasks.filter(status='pending').first()
        if task_e2:
            task_e2.status = 'done'
            task_e2.save()
            created_summary['tasks_done'] += 1

        self.stdout.write(f"  [OK]Evento 2: {event2.name}")

        # ── EVENTO 3: Cumpleaños Sofía — Celebración Equipo ──────────────────
        template_social = EventTemplate.objects.filter(name='Evento Social / Celebración').first()
        event3, e3_created = Event.objects.get_or_create(
            name='Cumpleaños Sofía — Celebración Equipo',
            owner=user,
            defaults={
                'status': 'active',
                'start_date': timezone.make_aware(
                    timezone.datetime.combine(today + timedelta(days=5), timezone.datetime.min.time())
                ),
                'template': template_social,
                'description': 'Celebración de cumpleaños de Sofía con todo el equipo.',
            },
        )
        if e3_created:
            created_summary['events'] += 1
            if template_social:
                apply_template_to_event(event3, template_social)

        # Agregar 15 asistentes (mix)
        attendees_data_3 = [
            ('Sofía Ramírez', 'sofia.r@equipo.com', 'confirmed'),
            ('Tomás Vargas', 'tomas@equipo.com', 'confirmed'),
            ('Elena Castillo', 'elena@equipo.com', 'confirmed'),
            ('Julián Herrera', 'julian@equipo.com', 'confirmed'),
            ('Valentina Ospina', 'valentina@equipo.com', 'confirmed'),
            ('Santiago Muñoz', 'santiago@equipo.com', 'confirmed'),
            ('Camila Londoño', 'camila@equipo.com', 'confirmed'),
            ('Diego Peña', 'diego@equipo.com', 'pending'),
            ('Mariana Cano', 'mariana@equipo.com', 'pending'),
            ('Simón Ávila', 'simon@equipo.com', 'pending'),
            ('Lucía Bermúdez', 'lucia@equipo.com', 'pending'),
            ('Nicolás Salazar', 'nicolas@equipo.com', 'pending'),
            ('Isabella Mejía', 'isabella@equipo.com', 'pending'),
            ('Emilio Guerrero', 'emilio@equipo.com', 'declined'),
            ('Paula Ríos', 'paula@equipo.com', 'confirmed'),
        ]
        for name, email, status in attendees_data_3:
            att, att_created = Attendee.objects.get_or_create(
                event=event3, email=email,
                defaults={'name': name, 'status': status},
            )
            if att_created:
                created_summary['attendees'] += 1

        # 0 tareas done (genera alerta de progreso bajo)
        self.stdout.write(f"  [OK]Evento 3: {event3.name} (genera alertas automáticamente)")

        # Ejecutar alert engine para generar alertas
        try:
            from events.services.alert_engine import run_alert_engine
            run_alert_engine(user)
            self.stdout.write('  [OK]Alertas generadas por el motor')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [WARN] Alert engine: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f"\nResumen seed_demo para '{username}':"
            f"\n  Eventos creados: {created_summary['events']}"
            f"\n  Asistentes agregados: {created_summary['attendees']}"
            f"\n  Tareas marcadas como done: {created_summary['tasks_done']}"
            f"\n  Ítems de presupuesto: {created_summary['budget_items']}"
        ))
