"""
Management command: seed_templates

Crea o actualiza las 3 plantillas base de BIND con tareas
y checklists predefinidos reales.

Uso: python manage.py seed_templates
"""

from django.core.management.base import BaseCommand
from events.models import EventTemplate, TemplateModule, TemplateTask, TemplateChecklistItem


TEMPLATES_DATA = [
    {
        'name': 'Conferencia Corporativa',
        'description': 'Plantilla para conferencias de negocios con agenda, ponentes y logística completa.',
        'category': 'business',
        'color': '#0D9488',
        'modules': ['tasks', 'attendees', 'checklist', 'files'],
        'tasks': [
            {'title': 'Definir agenda y ponentes', 'priority': 'high', 'days_before_event': 45, 'order': 1},
            {'title': 'Reservar el espacio/sala', 'priority': 'high', 'days_before_event': 40, 'order': 2},
            {'title': 'Diseñar material de comunicación', 'priority': 'medium', 'days_before_event': 30, 'order': 3},
            {'title': 'Enviar invitaciones', 'priority': 'high', 'days_before_event': 25, 'order': 4},
            {'title': 'Confirmar ponentes y temas', 'priority': 'high', 'days_before_event': 20, 'order': 5},
            {'title': 'Coordinar catering/refrigerios', 'priority': 'medium', 'days_before_event': 15, 'order': 6},
            {'title': 'Preparar equipos audiovisuales', 'priority': 'medium', 'days_before_event': 7, 'order': 7},
            {'title': 'Confirmación final de asistentes', 'priority': 'high', 'days_before_event': 5, 'order': 8},
            {'title': 'Brief al equipo de apoyo', 'priority': 'high', 'days_before_event': 2, 'order': 9},
            {'title': 'Verificar setup del lugar', 'priority': 'high', 'days_before_event': 1, 'order': 10},
        ],
        'checklist_items': [
            {'checklist_title': 'Logística del evento', 'item_text': '¿Espacio reservado y confirmado?', 'order': 1},
            {'checklist_title': 'Logística del evento', 'item_text': '¿Equipos audiovisuales probados?', 'order': 2},
            {'checklist_title': 'Logística del evento', 'item_text': '¿Señalética y accesos listos?', 'order': 3},
            {'checklist_title': 'Logística del evento', 'item_text': '¿Plan de contingencia definido?', 'order': 4},
            {'checklist_title': 'Comunicación', 'item_text': '¿Invitaciones enviadas?', 'order': 1},
            {'checklist_title': 'Comunicación', 'item_text': '¿Recordatorio enviado 48h antes?', 'order': 2},
            {'checklist_title': 'Comunicación', 'item_text': '¿Agenda publicada o distribuida?', 'order': 3},
        ],
    },
    {
        'name': 'Lanzamiento de Producto',
        'description': 'Plantilla para lanzamientos de producto con coordinación de prensa, demos y stakeholders.',
        'category': 'marketing',
        'color': '#7C3AED',
        'modules': ['tasks', 'attendees', 'checklist', 'files'],
        'tasks': [
            {'title': 'Definir mensaje clave del lanzamiento', 'priority': 'high', 'days_before_event': 60, 'order': 1},
            {'title': 'Crear materiales de prensa y marketing', 'priority': 'high', 'days_before_event': 45, 'order': 2},
            {'title': 'Coordinar con equipo de ventas', 'priority': 'medium', 'days_before_event': 30, 'order': 3},
            {'title': 'Preparar demo o prototipo', 'priority': 'high', 'days_before_event': 20, 'order': 4},
            {'title': 'Invitar prensa y stakeholders', 'priority': 'high', 'days_before_event': 15, 'order': 5},
            {'title': 'Preparar kit de prensa', 'priority': 'medium', 'days_before_event': 10, 'order': 6},
            {'title': 'Ensayo general de presentación', 'priority': 'high', 'days_before_event': 3, 'order': 7},
            {'title': 'Verificar materiales y demos', 'priority': 'high', 'days_before_event': 1, 'order': 8},
        ],
        'checklist_items': [
            {'checklist_title': 'Materiales listos', 'item_text': '¿Landing page o ficha del producto activa?', 'order': 1},
            {'checklist_title': 'Materiales listos', 'item_text': '¿Demo funcional y probada?', 'order': 2},
            {'checklist_title': 'Materiales listos', 'item_text': '¿Kit de prensa preparado?', 'order': 3},
            {'checklist_title': 'Materiales listos', 'item_text': '¿Redes sociales programadas?', 'order': 4},
            {'checklist_title': 'Equipo alineado', 'item_text': '¿Todos conocen el mensaje clave?', 'order': 1},
            {'checklist_title': 'Equipo alineado', 'item_text': '¿Roles del día definidos?', 'order': 2},
        ],
    },
    {
        'name': 'Evento Social / Celebración',
        'description': 'Plantilla para eventos sociales, celebraciones y reuniones informales.',
        'category': 'social',
        'color': '#F59E0B',
        'modules': ['tasks', 'attendees', 'checklist'],
        'tasks': [
            {'title': 'Definir lista de invitados', 'priority': 'medium', 'days_before_event': 30, 'order': 1},
            {'title': 'Reservar lugar o espacio', 'priority': 'high', 'days_before_event': 25, 'order': 2},
            {'title': 'Enviar invitaciones', 'priority': 'high', 'days_before_event': 20, 'order': 3},
            {'title': 'Coordinar decoración', 'priority': 'low', 'days_before_event': 10, 'order': 4},
            {'title': 'Confirmar catering o comida', 'priority': 'high', 'days_before_event': 7, 'order': 5},
            {'title': 'Confirmar asistencias', 'priority': 'medium', 'days_before_event': 5, 'order': 6},
            {'title': 'Compras de último momento', 'priority': 'medium', 'days_before_event': 1, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Día del evento', 'item_text': '¿Lugar decorado y listo?', 'order': 1},
            {'checklist_title': 'Día del evento', 'item_text': '¿Comida/bebida confirmada?', 'order': 2},
            {'checklist_title': 'Día del evento', 'item_text': '¿Música o entretenimiento listo?', 'order': 3},
            {'checklist_title': 'Día del evento', 'item_text': '¿Lista de invitados a mano?', 'order': 4},
        ],
    },
]


class Command(BaseCommand):
    help = 'Crea o actualiza las plantillas base de BIND con tareas y checklists predefinidos.'

    def handle(self, *args, **options):
        total_tasks = 0
        total_checklist_items = 0

        for tpl_data in TEMPLATES_DATA:
            template, created = EventTemplate.objects.get_or_create(
                name=tpl_data['name'],
                defaults={
                    'description': tpl_data['description'],
                    'category': tpl_data['category'],
                    'color': tpl_data['color'],
                    'created_by': None,
                },
            )
            action = 'Creada' if created else 'Actualizada'
            self.stdout.write(f"  {action}: {template.name}")

            # Módulos
            for module_type in tpl_data['modules']:
                TemplateModule.objects.get_or_create(
                    template=template,
                    module_type=module_type,
                )

            # Tareas predefinidas
            for task_data in tpl_data['tasks']:
                _, task_created = TemplateTask.objects.get_or_create(
                    template=template,
                    title=task_data['title'],
                    defaults={
                        'priority': task_data['priority'],
                        'days_before_event': task_data['days_before_event'],
                        'order': task_data['order'],
                    },
                )
                if task_created:
                    total_tasks += 1

            # Ítems de checklist predefinidos
            for item_data in tpl_data['checklist_items']:
                _, item_created = TemplateChecklistItem.objects.get_or_create(
                    template=template,
                    checklist_title=item_data['checklist_title'],
                    item_text=item_data['item_text'],
                    defaults={'order': item_data['order']},
                )
                if item_created:
                    total_checklist_items += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nPlantillas creadas/actualizadas: {total_tasks} tareas, {total_checklist_items} checklist items"
        ))
