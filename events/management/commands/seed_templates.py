"""
Management command: seed_templates

Crea o actualiza las 3 plantillas base de BIND con tareas,
checklists e ítems de presupuesto predefinidos reales.

Uso: python manage.py seed_templates
"""

from django.core.management.base import BaseCommand
from events.models import (
    EventTemplate, TemplateModule,
    TemplateTask, TemplateChecklistItem, TemplateBudgetItem,
)


TEMPLATES_DATA = [
    {
        'name': 'Conferencia Corporativa',
        'description': 'Plantilla para conferencias de negocios con agenda, ponentes y logística completa.',
        'category': 'business',
        'color': '#0D9488',
        'modules': ['tasks', 'attendees', 'checklist', 'files', 'budget'],
        'tasks': [
            {'title': 'Definir agenda y ponentes',          'priority': 'high',   'days_before_event': 45, 'order': 1},
            {'title': 'Reservar el espacio/sala',           'priority': 'high',   'days_before_event': 40, 'order': 2},
            {'title': 'Diseñar material de comunicación',   'priority': 'medium', 'days_before_event': 30, 'order': 3},
            {'title': 'Enviar invitaciones',                'priority': 'high',   'days_before_event': 25, 'order': 4},
            {'title': 'Confirmar ponentes y temas',         'priority': 'high',   'days_before_event': 20, 'order': 5},
            {'title': 'Coordinar catering/refrigerios',     'priority': 'medium', 'days_before_event': 15, 'order': 6},
            {'title': 'Preparar equipos audiovisuales',     'priority': 'medium', 'days_before_event':  7, 'order': 7},
            {'title': 'Confirmación final de asistentes',   'priority': 'high',   'days_before_event':  5, 'order': 8},
            {'title': 'Brief al equipo de apoyo',           'priority': 'high',   'days_before_event':  2, 'order': 9},
            {'title': 'Verificar setup del lugar',          'priority': 'high',   'days_before_event':  1, 'order': 10},
        ],
        'checklist_items': [
            {'checklist_title': 'Logística del evento', 'item_text': '¿Espacio reservado y confirmado?',   'order': 1},
            {'checklist_title': 'Logística del evento', 'item_text': '¿Equipos audiovisuales probados?',   'order': 2},
            {'checklist_title': 'Logística del evento', 'item_text': '¿Señalética y accesos listos?',      'order': 3},
            {'checklist_title': 'Logística del evento', 'item_text': '¿Plan de contingencia definido?',    'order': 4},
            {'checklist_title': 'Comunicación',         'item_text': '¿Invitaciones enviadas?',            'order': 1},
            {'checklist_title': 'Comunicación',         'item_text': '¿Recordatorio enviado 48h antes?',   'order': 2},
            {'checklist_title': 'Comunicación',         'item_text': '¿Agenda publicada o distribuida?',   'order': 3},
        ],
        'budget_items': [
            # Gastos
            {'name': 'Alquiler de espacio/sala',      'amount': 3_000_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Catering y refrigerios',        'amount': 1_500_000, 'type': 'expense', 'category': 'catering',   'order': 2},
            {'name': 'Material impreso (agenda, badges)', 'amount': 400_000, 'type': 'expense', 'category': 'marketing', 'order': 3},
            {'name': 'Equipos audiovisuales',         'amount':   800_000, 'type': 'expense', 'category': 'technology', 'order': 4},
            {'name': 'Personal de apoyo',             'amount':   600_000, 'type': 'expense', 'category': 'staff',      'order': 5},
            {'name': 'Transporte y logística',        'amount':   300_000, 'type': 'expense', 'category': 'transport',  'order': 6},
            # Ingresos
            {'name': 'Inscripciones de asistentes',   'amount': 5_000_000, 'type': 'income',  'category': 'other',      'order': 7},
            {'name': 'Patrocinio corporativo',        'amount': 2_000_000, 'type': 'income',  'category': 'marketing',  'order': 8},
        ],
    },
    {
        'name': 'Lanzamiento de Producto',
        'description': 'Plantilla para lanzamientos de producto con coordinación de prensa, demos y stakeholders.',
        'category': 'marketing',
        'color': '#7C3AED',
        'modules': ['tasks', 'attendees', 'checklist', 'files', 'budget'],
        'tasks': [
            {'title': 'Definir mensaje clave del lanzamiento', 'priority': 'high',   'days_before_event': 60, 'order': 1},
            {'title': 'Crear materiales de prensa y marketing','priority': 'high',   'days_before_event': 45, 'order': 2},
            {'title': 'Coordinar con equipo de ventas',        'priority': 'medium', 'days_before_event': 30, 'order': 3},
            {'title': 'Preparar demo o prototipo',             'priority': 'high',   'days_before_event': 20, 'order': 4},
            {'title': 'Invitar prensa y stakeholders',         'priority': 'high',   'days_before_event': 15, 'order': 5},
            {'title': 'Preparar kit de prensa',                'priority': 'medium', 'days_before_event': 10, 'order': 6},
            {'title': 'Ensayo general de presentación',        'priority': 'high',   'days_before_event':  3, 'order': 7},
            {'title': 'Verificar materiales y demos',          'priority': 'high',   'days_before_event':  1, 'order': 8},
        ],
        'checklist_items': [
            {'checklist_title': 'Materiales listos', 'item_text': '¿Landing page o ficha del producto activa?', 'order': 1},
            {'checklist_title': 'Materiales listos', 'item_text': '¿Demo funcional y probada?',                 'order': 2},
            {'checklist_title': 'Materiales listos', 'item_text': '¿Kit de prensa preparado?',                  'order': 3},
            {'checklist_title': 'Materiales listos', 'item_text': '¿Redes sociales programadas?',               'order': 4},
            {'checklist_title': 'Equipo alineado',   'item_text': '¿Todos conocen el mensaje clave?',           'order': 1},
            {'checklist_title': 'Equipo alineado',   'item_text': '¿Roles del día definidos?',                  'order': 2},
        ],
        'budget_items': [
            # Gastos
            {'name': 'Venue del lanzamiento',              'amount': 2_000_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Diseño y producción de materiales',  'amount': 1_200_000, 'type': 'expense', 'category': 'marketing',  'order': 2},
            {'name': 'Catering cóctel de lanzamiento',     'amount': 1_800_000, 'type': 'expense', 'category': 'catering',   'order': 3},
            {'name': 'Fotografía y video profesional',     'amount':   900_000, 'type': 'expense', 'category': 'technology', 'order': 4},
            {'name': 'Kit de prensa (impresión)',           'amount':   500_000, 'type': 'expense', 'category': 'marketing',  'order': 5},
            {'name': 'Personal de apoyo y presentadores',  'amount':   800_000, 'type': 'expense', 'category': 'staff',      'order': 6},
            # Ingresos
            {'name': 'Presupuesto de marketing asignado',  'amount': 8_000_000, 'type': 'income',  'category': 'other',      'order': 7},
        ],
    },
    {
        'name': 'Evento Social / Celebración',
        'description': 'Plantilla para eventos sociales, celebraciones y reuniones informales.',
        'category': 'social',
        'color': '#F59E0B',
        'modules': ['tasks', 'attendees', 'checklist', 'budget'],
        'tasks': [
            {'title': 'Definir lista de invitados',  'priority': 'medium', 'days_before_event': 30, 'order': 1},
            {'title': 'Reservar lugar o espacio',    'priority': 'high',   'days_before_event': 25, 'order': 2},
            {'title': 'Enviar invitaciones',         'priority': 'high',   'days_before_event': 20, 'order': 3},
            {'title': 'Coordinar decoración',        'priority': 'low',    'days_before_event': 10, 'order': 4},
            {'title': 'Confirmar catering o comida', 'priority': 'high',   'days_before_event':  7, 'order': 5},
            {'title': 'Confirmar asistencias',       'priority': 'medium', 'days_before_event':  5, 'order': 6},
            {'title': 'Compras de último momento',   'priority': 'medium', 'days_before_event':  1, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Día del evento', 'item_text': '¿Lugar decorado y listo?',           'order': 1},
            {'checklist_title': 'Día del evento', 'item_text': '¿Comida/bebida confirmada?',          'order': 2},
            {'checklist_title': 'Día del evento', 'item_text': '¿Música o entretenimiento listo?',    'order': 3},
            {'checklist_title': 'Día del evento', 'item_text': '¿Lista de invitados a mano?',         'order': 4},
        ],
        'budget_items': [
            # Gastos
            {'name': 'Alquiler del lugar',           'amount':   500_000, 'type': 'expense', 'category': 'venue',    'order': 1},
            {'name': 'Catering, comida y bebidas',   'amount':   800_000, 'type': 'expense', 'category': 'catering', 'order': 2},
            {'name': 'Decoración y ambientación',    'amount':   300_000, 'type': 'expense', 'category': 'other',    'order': 3},
            {'name': 'Entretenimiento / música',     'amount':   400_000, 'type': 'expense', 'category': 'other',    'order': 4},
        ],
    },
    # --- business 2/3 ---
    {
        'name': 'Reunión de Directivos',
        'description': 'Plantilla para juntas y reuniones estratégicas de alta dirección con actas y seguimiento de acuerdos.',
        'category': 'business',
        'color': '#1D4ED8',
        'modules': ['tasks', 'checklist', 'files'],
        'tasks': [
            {'title': 'Definir orden del día',                  'priority': 'high',   'days_before_event': 14, 'order': 1},
            {'title': 'Enviar convocatoria formal',             'priority': 'high',   'days_before_event': 10, 'order': 2},
            {'title': 'Preparar informes y presentaciones',     'priority': 'high',   'days_before_event':  5, 'order': 3},
            {'title': 'Confirmar asistencia de directivos',     'priority': 'medium', 'days_before_event':  3, 'order': 4},
            {'title': 'Preparar sala y equipos',                'priority': 'medium', 'days_before_event':  1, 'order': 5},
            {'title': 'Redactar acta de la reunion',            'priority': 'high',   'days_before_event':  0, 'order': 6},
            {'title': 'Distribuir acuerdos y responsables',     'priority': 'high',   'days_before_event':  0, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Antes de la reunion',  'item_text': 'Orden del dia enviado a todos',           'order': 1},
            {'checklist_title': 'Antes de la reunion',  'item_text': 'Informes previos distribuidos',           'order': 2},
            {'checklist_title': 'Antes de la reunion',  'item_text': 'Quorum confirmado',                       'order': 3},
            {'checklist_title': 'Despues de la reunion','item_text': 'Acta redactada y firmada',                'order': 1},
            {'checklist_title': 'Despues de la reunion','item_text': 'Acuerdos con responsable y fecha limite', 'order': 2},
        ],
        'budget_items': [
            {'name': 'Sala de reunion (alquiler)',    'amount':  500_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Catering ejecutivo',            'amount':  400_000, 'type': 'expense', 'category': 'catering',   'order': 2},
            {'name': 'Impresion de documentos',       'amount':   80_000, 'type': 'expense', 'category': 'other',      'order': 3},
        ],
    },
    # --- business 3/3 ---
    {
        'name': 'Capacitacion Interna',
        'description': 'Plantilla para talleres y jornadas de formacion para equipos de trabajo dentro de la empresa.',
        'category': 'business',
        'color': '#0369A1',
        'modules': ['tasks', 'attendees', 'checklist', 'files'],
        'tasks': [
            {'title': 'Definir objetivos de aprendizaje',       'priority': 'high',   'days_before_event': 21, 'order': 1},
            {'title': 'Seleccionar facilitador o instructor',    'priority': 'high',   'days_before_event': 18, 'order': 2},
            {'title': 'Preparar material didactico',             'priority': 'high',   'days_before_event': 10, 'order': 3},
            {'title': 'Inscribir participantes',                 'priority': 'medium', 'days_before_event':  7, 'order': 4},
            {'title': 'Enviar recordatorio con materiales',      'priority': 'low',    'days_before_event':  2, 'order': 5},
            {'title': 'Preparar encuesta de satisfaccion',       'priority': 'medium', 'days_before_event':  1, 'order': 6},
            {'title': 'Enviar certificados de participacion',    'priority': 'medium', 'days_before_event':  0, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Logistica',     'item_text': 'Sala o plataforma virtual lista',         'order': 1},
            {'checklist_title': 'Logistica',     'item_text': 'Material enviado a participantes',        'order': 2},
            {'checklist_title': 'Logistica',     'item_text': 'Equipos de proyeccion probados',          'order': 3},
            {'checklist_title': 'Post-evento',   'item_text': 'Encuesta de satisfaccion aplicada',       'order': 1},
            {'checklist_title': 'Post-evento',   'item_text': 'Certificados emitidos',                   'order': 2},
            {'checklist_title': 'Post-evento',   'item_text': 'Informe de resultados elaborado',         'order': 3},
        ],
        'budget_items': [
            {'name': 'Instructor / facilitador',  'amount':  800_000, 'type': 'expense', 'category': 'staff',      'order': 1},
            {'name': 'Material impreso',          'amount':  150_000, 'type': 'expense', 'category': 'marketing',  'order': 2},
            {'name': 'Refrigerios',               'amount':  300_000, 'type': 'expense', 'category': 'catering',   'order': 3},
            {'name': 'Plataforma e-learning',     'amount':  200_000, 'type': 'expense', 'category': 'technology', 'order': 4},
        ],
    },
    # --- academic 1/3 ---
    {
        'name': 'Defensa de Tesis',
        'description': 'Plantilla para la organizacion y seguimiento de una defensa de tesis o trabajo de grado.',
        'category': 'academic',
        'color': '#374151',
        'modules': ['tasks', 'checklist', 'files'],
        'tasks': [
            {'title': 'Entregar borrador final al asesor',       'priority': 'high',   'days_before_event': 30, 'order': 1},
            {'title': 'Incorporar correcciones del asesor',      'priority': 'high',   'days_before_event': 20, 'order': 2},
            {'title': 'Solicitar fecha y jurado',                'priority': 'high',   'days_before_event': 15, 'order': 3},
            {'title': 'Enviar documento final al jurado',        'priority': 'high',   'days_before_event': 10, 'order': 4},
            {'title': 'Preparar presentacion de diapositivas',   'priority': 'high',   'days_before_event':  7, 'order': 5},
            {'title': 'Ensayar defensa oral',                    'priority': 'medium', 'days_before_event':  3, 'order': 6},
            {'title': 'Preparar documentos administrativos',     'priority': 'medium', 'days_before_event':  2, 'order': 7},
            {'title': 'Verificar sala y equipos el dia anterior','priority': 'high',   'days_before_event':  1, 'order': 8},
        ],
        'checklist_items': [
            {'checklist_title': 'Documento',      'item_text': 'Formato de tesis cumple normas institucionales', 'order': 1},
            {'checklist_title': 'Documento',      'item_text': 'Bibliografia completa y citada correctamente',   'order': 2},
            {'checklist_title': 'Documento',      'item_text': 'Firma del asesor en el documento oficial',       'order': 3},
            {'checklist_title': 'Presentacion',   'item_text': 'Diapositivas revisadas por asesor',              'order': 1},
            {'checklist_title': 'Presentacion',   'item_text': 'Tiempo de exposicion ensayado',                  'order': 2},
            {'checklist_title': 'Presentacion',   'item_text': 'Copia de respaldo en USB y nube',                'order': 3},
        ],
        'budget_items': [
            {'name': 'Impresion y empastado de tesis',  'amount': 200_000, 'type': 'expense', 'category': 'other',   'order': 1},
            {'name': 'Derechos de grado',               'amount': 500_000, 'type': 'expense', 'category': 'other',   'order': 2},
        ],
    },
    # --- academic 2/3 ---
    {
        'name': 'Congreso Academico',
        'description': 'Plantilla para organizar congresos, simposios o jornadas academicas con ponencias y mesas de trabajo.',
        'category': 'academic',
        'color': '#4B5563',
        'modules': ['tasks', 'attendees', 'checklist', 'files', 'budget'],
        'tasks': [
            {'title': 'Definir tematica y comite cientifico',    'priority': 'high',   'days_before_event': 90, 'order': 1},
            {'title': 'Lanzar convocatoria de ponencias',        'priority': 'high',   'days_before_event': 75, 'order': 2},
            {'title': 'Evaluar y seleccionar ponencias',         'priority': 'high',   'days_before_event': 50, 'order': 3},
            {'title': 'Confirmar ponentes seleccionados',        'priority': 'high',   'days_before_event': 40, 'order': 4},
            {'title': 'Disenar programa academico',              'priority': 'medium', 'days_before_event': 30, 'order': 5},
            {'title': 'Abrir inscripciones de asistentes',       'priority': 'medium', 'days_before_event': 30, 'order': 6},
            {'title': 'Coordinar logistica del recinto',         'priority': 'medium', 'days_before_event': 14, 'order': 7},
            {'title': 'Preparar memorias del congreso',          'priority': 'low',    'days_before_event':  7, 'order': 8},
            {'title': 'Acreditar asistentes el dia del evento',  'priority': 'high',   'days_before_event':  0, 'order': 9},
        ],
        'checklist_items': [
            {'checklist_title': 'Programa academico', 'item_text': 'Programa publicado en la web',                'order': 1},
            {'checklist_title': 'Programa academico', 'item_text': 'Ponentes confirmados con horario',            'order': 2},
            {'checklist_title': 'Programa academico', 'item_text': 'Moderadores asignados por sala',              'order': 3},
            {'checklist_title': 'Logistica',          'item_text': 'Salas equipadas con proyector y microfono',   'order': 1},
            {'checklist_title': 'Logistica',          'item_text': 'Credenciales y material de bienvenida listo', 'order': 2},
            {'checklist_title': 'Logistica',          'item_text': 'Servicio de catering coordinado',             'order': 3},
        ],
        'budget_items': [
            {'name': 'Alquiler de recinto',               'amount': 5_000_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Catering y coffee breaks',          'amount': 2_500_000, 'type': 'expense', 'category': 'catering',   'order': 2},
            {'name': 'Material impreso (programa, actas)','amount':   600_000, 'type': 'expense', 'category': 'marketing',  'order': 3},
            {'name': 'Equipos audiovisuales',             'amount': 1_000_000, 'type': 'expense', 'category': 'technology', 'order': 4},
            {'name': 'Inscripciones de asistentes',       'amount': 8_000_000, 'type': 'income',  'category': 'other',      'order': 5},
            {'name': 'Patrocinio institucional',          'amount': 3_000_000, 'type': 'income',  'category': 'other',      'order': 6},
        ],
    },
    # --- academic 3/3 ---
    {
        'name': 'Feria de Ciencias',
        'description': 'Plantilla para organizar ferias y exposiciones de proyectos cientificos y tecnologicos estudiantiles.',
        'category': 'academic',
        'color': '#065F46',
        'modules': ['tasks', 'attendees', 'checklist', 'budget'],
        'tasks': [
            {'title': 'Publicar bases y convocatoria',           'priority': 'high',   'days_before_event': 45, 'order': 1},
            {'title': 'Recibir inscripciones de proyectos',      'priority': 'high',   'days_before_event': 30, 'order': 2},
            {'title': 'Asignar espacios a cada proyecto',        'priority': 'medium', 'days_before_event': 14, 'order': 3},
            {'title': 'Conformar jurado evaluador',              'priority': 'high',   'days_before_event': 10, 'order': 4},
            {'title': 'Preparar rubrica de evaluacion',          'priority': 'medium', 'days_before_event':  7, 'order': 5},
            {'title': 'Montar stands y senaletica',              'priority': 'medium', 'days_before_event':  1, 'order': 6},
            {'title': 'Ceremonia de premiacion',                 'priority': 'high',   'days_before_event':  0, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Organizacion',  'item_text': 'Bases del concurso publicadas',               'order': 1},
            {'checklist_title': 'Organizacion',  'item_text': 'Jurado confirmado y capacitado',              'order': 2},
            {'checklist_title': 'Organizacion',  'item_text': 'Premios y diplomas preparados',               'order': 3},
            {'checklist_title': 'Dia del evento','item_text': 'Stands montados y numerados',                 'order': 1},
            {'checklist_title': 'Dia del evento','item_text': 'Planillas de evaluacion impresas',            'order': 2},
            {'checklist_title': 'Dia del evento','item_text': 'Fotografia y cobertura coordinada',           'order': 3},
        ],
        'budget_items': [
            {'name': 'Trofeos y diplomas',           'amount':  400_000, 'type': 'expense', 'category': 'other',      'order': 1},
            {'name': 'Materiales para stands',       'amount':  300_000, 'type': 'expense', 'category': 'other',      'order': 2},
            {'name': 'Refrigerios',                  'amount':  500_000, 'type': 'expense', 'category': 'catering',   'order': 3},
            {'name': 'Patrocinio empresarial',       'amount': 1_500_000,'type': 'income',  'category': 'other',      'order': 4},
        ],
    },
    # --- creative 1/3 ---
    {
        'name': 'Exposicion de Arte',
        'description': 'Plantilla para montar una exposicion de obras artisticas con curaduría, montaje y apertura al publico.',
        'category': 'creative',
        'color': '#7C3AED',
        'modules': ['tasks', 'attendees', 'checklist', 'files', 'budget'],
        'tasks': [
            {'title': 'Definir concepto curatorial',             'priority': 'high',   'days_before_event': 60, 'order': 1},
            {'title': 'Seleccionar artistas y obras',            'priority': 'high',   'days_before_event': 45, 'order': 2},
            {'title': 'Gestionar permisos y seguros de obras',   'priority': 'high',   'days_before_event': 30, 'order': 3},
            {'title': 'Diseno de catalogo y material grafico',   'priority': 'medium', 'days_before_event': 20, 'order': 4},
            {'title': 'Coordinar transporte de obras',           'priority': 'high',   'days_before_event': 10, 'order': 5},
            {'title': 'Montaje y curaduría en sala',             'priority': 'high',   'days_before_event':  3, 'order': 6},
            {'title': 'Vernissage / inauguracion',               'priority': 'high',   'days_before_event':  0, 'order': 7},
            {'title': 'Desmontaje y devolucion de obras',        'priority': 'medium', 'days_before_event': -7, 'order': 8},
        ],
        'checklist_items': [
            {'checklist_title': 'Montaje',      'item_text': 'Obras inventariadas y registradas',                'order': 1},
            {'checklist_title': 'Montaje',      'item_text': 'Iluminacion de sala ajustada por obra',            'order': 2},
            {'checklist_title': 'Montaje',      'item_text': 'Cedulas y textos curatoriales instalados',         'order': 3},
            {'checklist_title': 'Comunicacion', 'item_text': 'Notas de prensa enviadas a medios',                'order': 1},
            {'checklist_title': 'Comunicacion', 'item_text': 'Evento publicado en redes sociales',               'order': 2},
            {'checklist_title': 'Comunicacion', 'item_text': 'Invitaciones de inauguracion enviadas',            'order': 3},
        ],
        'budget_items': [
            {'name': 'Alquiler de galeria',           'amount': 1_500_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Catalogo impreso',              'amount':   600_000, 'type': 'expense', 'category': 'marketing',  'order': 2},
            {'name': 'Transporte y embalaje de obras','amount':   800_000, 'type': 'expense', 'category': 'transport',  'order': 3},
            {'name': 'Catering inauguracion',         'amount':   500_000, 'type': 'expense', 'category': 'catering',   'order': 4},
            {'name': 'Venta de obras (comision)',     'amount': 3_000_000, 'type': 'income',  'category': 'other',      'order': 5},
            {'name': 'Patrocinio cultural',           'amount': 1_000_000, 'type': 'income',  'category': 'other',      'order': 6},
        ],
    },
    # --- creative 2/3 ---
    {
        'name': 'Produccion Musical',
        'description': 'Plantilla para la organizacion de un concierto, recital o presentacion en vivo de musica.',
        'category': 'creative',
        'color': '#6D28D9',
        'modules': ['tasks', 'attendees', 'checklist', 'budget'],
        'tasks': [
            {'title': 'Confirmar artistas y repertorio',         'priority': 'high',   'days_before_event': 45, 'order': 1},
            {'title': 'Contratar venue y equipo tecnico',        'priority': 'high',   'days_before_event': 40, 'order': 2},
            {'title': 'Diseno de flyers y difusion',             'priority': 'medium', 'days_before_event': 30, 'order': 3},
            {'title': 'Abrir venta de entradas',                 'priority': 'high',   'days_before_event': 25, 'order': 4},
            {'title': 'Coordinar backline y rider tecnico',      'priority': 'high',   'days_before_event': 10, 'order': 5},
            {'title': 'Ensayo general en el venue',              'priority': 'high',   'days_before_event':  1, 'order': 6},
            {'title': 'Prueba de sonido y luces',                'priority': 'high',   'days_before_event':  1, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Tecnico',   'item_text': 'Sistema de sonido instalado y probado',          'order': 1},
            {'checklist_title': 'Tecnico',   'item_text': 'Iluminacion de escenario lista',                 'order': 2},
            {'checklist_title': 'Tecnico',   'item_text': 'Backline confirmado con artistas',               'order': 3},
            {'checklist_title': 'Logistica', 'item_text': 'Control de acceso y boleteria organizado',       'order': 1},
            {'checklist_title': 'Logistica', 'item_text': 'Camerino y hospitality para artistas listos',    'order': 2},
            {'checklist_title': 'Logistica', 'item_text': 'Seguridad y primeros auxilios coordinados',      'order': 3},
        ],
        'budget_items': [
            {'name': 'Cache artistas',            'amount': 3_000_000, 'type': 'expense', 'category': 'staff',      'order': 1},
            {'name': 'Alquiler del venue',        'amount': 2_000_000, 'type': 'expense', 'category': 'venue',      'order': 2},
            {'name': 'Equipo de sonido y luces',  'amount': 1_500_000, 'type': 'expense', 'category': 'technology', 'order': 3},
            {'name': 'Publicidad y difusion',     'amount':   700_000, 'type': 'expense', 'category': 'marketing',  'order': 4},
            {'name': 'Venta de entradas',         'amount': 8_000_000, 'type': 'income',  'category': 'other',      'order': 5},
            {'name': 'Patrocinio de marca',       'amount': 1_500_000, 'type': 'income',  'category': 'marketing',  'order': 6},
        ],
    },
    # --- creative 3/3 ---
    {
        'name': 'Taller de Diseno Creativo',
        'description': 'Plantilla para talleres practicos de diseno, ilustracion o cualquier disciplina creativa con dinamicas colaborativas.',
        'category': 'creative',
        'color': '#9333EA',
        'modules': ['tasks', 'attendees', 'checklist', 'files'],
        'tasks': [
            {'title': 'Definir tematica y metodologia del taller','priority': 'high',   'days_before_event': 21, 'order': 1},
            {'title': 'Preparar guia y materiales didacticos',    'priority': 'high',   'days_before_event': 14, 'order': 2},
            {'title': 'Abrir inscripciones',                     'priority': 'medium', 'days_before_event': 10, 'order': 3},
            {'title': 'Conseguir materiales y herramientas',     'priority': 'medium', 'days_before_event':  7, 'order': 4},
            {'title': 'Enviar indicaciones a los participantes', 'priority': 'low',    'days_before_event':  2, 'order': 5},
            {'title': 'Montar el espacio de trabajo',            'priority': 'medium', 'days_before_event':  1, 'order': 6},
            {'title': 'Documentar resultados y obras del taller','priority': 'low',    'days_before_event':  0, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Materiales',  'item_text': 'Materiales listos y organizados por puesto',    'order': 1},
            {'checklist_title': 'Materiales',  'item_text': 'Guia del taller impresa o digital disponible',  'order': 2},
            {'checklist_title': 'Espacio',     'item_text': 'Mesas y sillas dispuestas para trabajo grupal', 'order': 1},
            {'checklist_title': 'Espacio',     'item_text': 'Buena iluminacion y ventilacion del lugar',     'order': 2},
            {'checklist_title': 'Espacio',     'item_text': 'Zona de exposicion de trabajos finales lista',  'order': 3},
        ],
        'budget_items': [
            {'name': 'Materiales artisticos',     'amount':  400_000, 'type': 'expense', 'category': 'other',    'order': 1},
            {'name': 'Facilitador o artista',     'amount':  600_000, 'type': 'expense', 'category': 'staff',    'order': 2},
            {'name': 'Alquiler del espacio',      'amount':  300_000, 'type': 'expense', 'category': 'venue',    'order': 3},
            {'name': 'Inscripciones',             'amount': 1_200_000,'type': 'income',  'category': 'other',    'order': 4},
        ],
    },
    # --- marketing 2/3 ---
    {
        'name': 'Feria Comercial / Expo',
        'description': 'Plantilla para la participacion o gestion de stands en ferias, expos y eventos B2B.',
        'category': 'marketing',
        'color': '#C2410C',
        'modules': ['tasks', 'attendees', 'checklist', 'files', 'budget'],
        'tasks': [
            {'title': 'Inscribir participacion en la feria',     'priority': 'high',   'days_before_event': 60, 'order': 1},
            {'title': 'Diseno y produccion del stand',           'priority': 'high',   'days_before_event': 30, 'order': 2},
            {'title': 'Preparar catalogo de productos',          'priority': 'medium', 'days_before_event': 20, 'order': 3},
            {'title': 'Capacitar al equipo comercial',           'priority': 'high',   'days_before_event': 14, 'order': 4},
            {'title': 'Preparar material POP y muestras',        'priority': 'medium', 'days_before_event':  7, 'order': 5},
            {'title': 'Montar el stand',                         'priority': 'high',   'days_before_event':  1, 'order': 6},
            {'title': 'Seguimiento de leads post-evento',        'priority': 'high',   'days_before_event': -3, 'order': 7},
        ],
        'checklist_items': [
            {'checklist_title': 'Stand',       'item_text': 'Grafica e imagen de marca instalada',          'order': 1},
            {'checklist_title': 'Stand',       'item_text': 'Pantalla o demo de producto funcionando',      'order': 2},
            {'checklist_title': 'Stand',       'item_text': 'Stock de muestras y material POP suficiente',  'order': 3},
            {'checklist_title': 'Comercial',   'item_text': 'Formulario de captura de leads listo',         'order': 1},
            {'checklist_title': 'Comercial',   'item_text': 'Equipo con uniforme o identificacion',         'order': 2},
            {'checklist_title': 'Comercial',   'item_text': 'Propuesta comercial lista para entregar',      'order': 3},
        ],
        'budget_items': [
            {'name': 'Inscripcion y espacio en la feria',   'amount': 3_000_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Diseno y montaje del stand',          'amount': 4_000_000, 'type': 'expense', 'category': 'marketing',  'order': 2},
            {'name': 'Material POP y muestras',             'amount': 1_500_000, 'type': 'expense', 'category': 'marketing',  'order': 3},
            {'name': 'Transporte y logistica',              'amount':   600_000, 'type': 'expense', 'category': 'transport',  'order': 4},
            {'name': 'Personal de atencion',                'amount': 1_000_000, 'type': 'expense', 'category': 'staff',      'order': 5},
            {'name': 'Ventas proyectadas en feria',         'amount':15_000_000, 'type': 'income',  'category': 'other',      'order': 6},
        ],
    },
    # --- marketing 3/3 ---
    {
        'name': 'Campana en Redes Sociales',
        'description': 'Plantilla para planificar y ejecutar una campana de marketing digital en redes sociales con metas y KPIs.',
        'category': 'marketing',
        'color': '#EA580C',
        'modules': ['tasks', 'checklist', 'files'],
        'tasks': [
            {'title': 'Definir objetivo y KPIs de la campana',   'priority': 'high',   'days_before_event': 21, 'order': 1},
            {'title': 'Identificar publico objetivo',            'priority': 'high',   'days_before_event': 18, 'order': 2},
            {'title': 'Crear calendario editorial',              'priority': 'high',   'days_before_event': 14, 'order': 3},
            {'title': 'Producir contenido (fotos, videos)',      'priority': 'high',   'days_before_event': 10, 'order': 4},
            {'title': 'Configurar pauta pagada',                 'priority': 'medium', 'days_before_event':  7, 'order': 5},
            {'title': 'Programar publicaciones',                 'priority': 'medium', 'days_before_event':  3, 'order': 6},
            {'title': 'Monitorear metricas durante la campana',  'priority': 'high',   'days_before_event':  0, 'order': 7},
            {'title': 'Informe final de resultados',             'priority': 'medium', 'days_before_event': -7, 'order': 8},
        ],
        'checklist_items': [
            {'checklist_title': 'Contenido',   'item_text': 'Copies y hashtags aprobados',                  'order': 1},
            {'checklist_title': 'Contenido',   'item_text': 'Artes visuales en formato correcto por red',   'order': 2},
            {'checklist_title': 'Contenido',   'item_text': 'Call to action definido en cada pieza',        'order': 3},
            {'checklist_title': 'Pauta',       'item_text': 'Presupuesto de ads asignado y aprobado',       'order': 1},
            {'checklist_title': 'Pauta',       'item_text': 'Segmentacion de audiencia configurada',        'order': 2},
            {'checklist_title': 'Pauta',       'item_text': 'Pixel de seguimiento instalado',               'order': 3},
        ],
        'budget_items': [
            {'name': 'Produccion de contenido',     'amount':   800_000, 'type': 'expense', 'category': 'marketing',  'order': 1},
            {'name': 'Pauta en redes sociales',     'amount': 1_500_000, 'type': 'expense', 'category': 'marketing',  'order': 2},
            {'name': 'Herramientas de gestion',     'amount':   200_000, 'type': 'expense', 'category': 'technology', 'order': 3},
            {'name': 'Presupuesto de marketing',    'amount': 3_000_000, 'type': 'income',  'category': 'other',      'order': 4},
        ],
    },
    # --- social 2/3 ---
    {
        'name': 'Boda',
        'description': 'Plantilla completa para la organizacion de una boda con todos los detalles logisticos, proveedores y cronograma.',
        'category': 'social',
        'color': '#BE185D',
        'modules': ['tasks', 'attendees', 'checklist', 'budget'],
        'tasks': [
            {'title': 'Definir fecha, lugar y presupuesto',      'priority': 'high',   'days_before_event': 180,'order': 1},
            {'title': 'Seleccionar y reservar salon',            'priority': 'high',   'days_before_event': 150,'order': 2},
            {'title': 'Contratar catering y pasteleria',         'priority': 'high',   'days_before_event': 120,'order': 3},
            {'title': 'Enviar invitaciones formales',            'priority': 'high',   'days_before_event':  90,'order': 4},
            {'title': 'Contratar fotografia y video',            'priority': 'high',   'days_before_event':  90,'order': 5},
            {'title': 'Coordinar musica y entretenimiento',      'priority': 'medium', 'days_before_event':  60,'order': 6},
            {'title': 'Confirmar lista final de invitados',      'priority': 'high',   'days_before_event':  30,'order': 7},
            {'title': 'Ensayo de ceremonia',                     'priority': 'high',   'days_before_event':   2,'order': 8},
            {'title': 'Confirmar todos los proveedores',         'priority': 'high',   'days_before_event':   1,'order': 9},
        ],
        'checklist_items': [
            {'checklist_title': 'Proveedores',    'item_text': 'Contrato de salon firmado',                  'order': 1},
            {'checklist_title': 'Proveedores',    'item_text': 'Menu de catering degustado y aprobado',      'order': 2},
            {'checklist_title': 'Proveedores',    'item_text': 'Fotografo/videografo confirmado',            'order': 3},
            {'checklist_title': 'Proveedores',    'item_text': 'Musica o DJ confirmado',                     'order': 4},
            {'checklist_title': 'Dia de la boda','item_text': 'Cronograma entregado a todos los involucrados','order': 1},
            {'checklist_title': 'Dia de la boda','item_text': 'Decoracion y flores instaladas',              'order': 2},
            {'checklist_title': 'Dia de la boda','item_text': 'Transporte de novios coordinado',             'order': 3},
        ],
        'budget_items': [
            {'name': 'Salon y decoracion',            'amount':15_000_000,'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Catering (banquete)',            'amount':20_000_000,'type': 'expense', 'category': 'catering',   'order': 2},
            {'name': 'Fotografia y video',            'amount': 5_000_000,'type': 'expense', 'category': 'technology', 'order': 3},
            {'name': 'Musica y entretenimiento',      'amount': 3_000_000,'type': 'expense', 'category': 'other',      'order': 4},
            {'name': 'Flores y decoracion floral',   'amount': 2_000_000,'type': 'expense', 'category': 'other',      'order': 5},
            {'name': 'Transporte',                    'amount': 1_000_000,'type': 'expense', 'category': 'transport',  'order': 6},
        ],
    },
    # --- social 3/3 ---
    {
        'name': 'Cena Benefica / Gala',
        'description': 'Plantilla para organizar cenas de gala, eventos de recaudacion de fondos o galas solidarias.',
        'category': 'social',
        'color': '#0F766E',
        'modules': ['tasks', 'attendees', 'checklist', 'budget'],
        'tasks': [
            {'title': 'Definir causa y meta de recaudacion',    'priority': 'high',   'days_before_event': 60, 'order': 1},
            {'title': 'Buscar y confirmar auspiciadores',       'priority': 'high',   'days_before_event': 45, 'order': 2},
            {'title': 'Reservar el salon de gala',              'priority': 'high',   'days_before_event': 40, 'order': 3},
            {'title': 'Diseno y envio de invitaciones de gala', 'priority': 'medium', 'days_before_event': 30, 'order': 4},
            {'title': 'Coordinar subasta o actividad de fondos','priority': 'high',   'days_before_event': 20, 'order': 5},
            {'title': 'Contratar animador o maestro de ceremonia','priority':'medium', 'days_before_event': 15, 'order': 6},
            {'title': 'Confirmar mesa de asistentes',           'priority': 'high',   'days_before_event':  7, 'order': 7},
            {'title': 'Preparar certificados y reconocimientos','priority': 'low',    'days_before_event':  3, 'order': 8},
        ],
        'checklist_items': [
            {'checklist_title': 'Gala',         'item_text': 'Mesa de registro de invitados lista',          'order': 1},
            {'checklist_title': 'Gala',         'item_text': 'Asignacion de mesas impresa',                  'order': 2},
            {'checklist_title': 'Gala',         'item_text': 'Programa de la noche impreso o digital',       'order': 3},
            {'checklist_title': 'Recaudacion',  'item_text': 'Lotes de subasta inventariados y valorados',   'order': 1},
            {'checklist_title': 'Recaudacion',  'item_text': 'Sistema de pago en sitio habilitado',          'order': 2},
            {'checklist_title': 'Recaudacion',  'item_text': 'Reporte de recaudacion listo para anunciar',   'order': 3},
        ],
        'budget_items': [
            {'name': 'Salon de gala',                 'amount': 6_000_000, 'type': 'expense', 'category': 'venue',      'order': 1},
            {'name': 'Cena y catering de gala',       'amount': 8_000_000, 'type': 'expense', 'category': 'catering',   'order': 2},
            {'name': 'Animador y produccion',         'amount': 2_000_000, 'type': 'expense', 'category': 'staff',      'order': 3},
            {'name': 'Decoracion y flores',           'amount': 1_500_000, 'type': 'expense', 'category': 'other',      'order': 4},
            {'name': 'Venta de mesas / boletas',      'amount':20_000_000, 'type': 'income',  'category': 'other',      'order': 5},
            {'name': 'Recaudacion por subasta',       'amount':10_000_000, 'type': 'income',  'category': 'other',      'order': 6},
            {'name': 'Patrocinio de empresas',        'amount': 5_000_000, 'type': 'income',  'category': 'other',      'order': 7},
        ],
    },
]


class Command(BaseCommand):
    help = 'Crea o actualiza las plantillas base de BIND con tareas, checklists e ítems de presupuesto.'

    def handle(self, *args, **options):
        total_tasks = 0
        total_checklist_items = 0
        total_budget_items = 0

        for tpl_data in TEMPLATES_DATA:
            template, created = EventTemplate.objects.get_or_create(
                name=tpl_data['name'],
                defaults={
                    'description': tpl_data['description'],
                    'category':    tpl_data['category'],
                    'color':       tpl_data['color'],
                    'created_by':  None,
                },
            )
            action = 'Creada' if created else 'Actualizada'
            self.stdout.write(f"  {action}: {template.name}")

            # Módulos (incluye 'budget' donde corresponde)
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
                        'priority':          task_data['priority'],
                        'days_before_event': task_data['days_before_event'],
                        'order':             task_data['order'],
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

            # Ítems de presupuesto predefinidos
            for bi_data in tpl_data['budget_items']:
                _, bi_created = TemplateBudgetItem.objects.get_or_create(
                    template=template,
                    name=bi_data['name'],
                    defaults={
                        'amount_estimate': bi_data['amount'],
                        'item_type':       bi_data['type'],
                        'category':        bi_data['category'],
                        'order':           bi_data['order'],
                    },
                )
                if bi_created:
                    total_budget_items += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nListo: {total_tasks} tareas, "
            f"{total_checklist_items} ítems de checklist, "
            f"{total_budget_items} ítems de presupuesto creados."
        ))
