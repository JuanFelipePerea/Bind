from django.db import models
from django.contrib.auth.models import User


class EventTemplate(models.Model):
    """
    Plantilla base para crear eventos rápidamente.
    Un EventTemplate puede usarse para generar múltiples Events.
    Relación: 1 EventTemplate → N Events
    """

    CATEGORY_CHOICES = [
        ('business', 'Negocios'),
        ('academic', 'Académico'),
        ('creative', 'Creativo'),
        ('marketing', 'Marketing'),
        ('social', 'Social'),
    ]

    name = models.CharField(max_length=100, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='business',
        verbose_name='Categoría'
    )
    color = models.CharField(
        max_length=7, default='#3B82F6',
        verbose_name='Color',
        help_text='Color representativo en formato hexadecimal (#RRGGBB).'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='templates', verbose_name='Creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Plantilla de evento"
        verbose_name_plural = "Plantillas de evento"
        ordering = ['-created_at']


class TemplateModule(models.Model):
    """
    Define qué módulos incluye una plantilla por defecto.
    Ej: la plantilla "Conferencia" activa: tasks, attendees, checklist, files, budget.
    Relación: 1 EventTemplate → N TemplateModules
    """

    MODULE_CHOICES = [
        ('tasks', 'Tareas'),
        ('attendees', 'Asistentes'),
        ('checklist', 'Checklist'),
        ('files', 'Archivos'),
        ('budget', 'Presupuesto'),
    ]

    template = models.ForeignKey(EventTemplate, on_delete=models.CASCADE, related_name='modules')
    module_type = models.CharField(max_length=20, choices=MODULE_CHOICES, verbose_name='Módulo')

    def __str__(self):
        return f"{self.template.name} → {self.module_type}"

    class Meta:
        verbose_name = "Módulo de plantilla"
        verbose_name_plural = "Módulos de plantilla"
        # Un módulo no puede repetirse en la misma plantilla
        unique_together = ('template', 'module_type')


class Event(models.Model):
    """
    Entidad central del sistema. Todo en BIND gira alrededor de un Event.
    Relación: 1 User → N Events (el owner es el organizador)
    Relación: 1 EventTemplate → N Events (template es opcional)
    """

    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
    ]

    name = models.CharField(max_length=150, verbose_name='Nombre del evento')
    description = models.TextField(blank=True, verbose_name='Descripción')
    location = models.CharField(max_length=200, blank=True, verbose_name='Lugar')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft',
        verbose_name='Estado'
    )
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de inicio')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de fin')
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='events', verbose_name='Organizador'
    )
    template = models.ForeignKey(
        EventTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='events',
        verbose_name='Plantilla base',
        help_text='Plantilla utilizada para crear este evento. Opcional.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering = ['-created_at']


class EventModule(models.Model):
    """
    Registra qué módulos están activos para un evento específico.
    Ej: el evento "Boda Ana & Luis" tiene activos: tasks, attendees, checklist, budget.
    Relación: 1 Event → N EventModules
    """

    MODULE_CHOICES = [
        ('tasks', 'Tareas'),
        ('attendees', 'Asistentes'),
        ('checklist', 'Checklist'),
        ('files', 'Archivos'),
        ('budget', 'Presupuesto'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='modules')
    module_type = models.CharField(max_length=20, choices=MODULE_CHOICES, verbose_name='Módulo')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    def __str__(self):
        return f"{self.event.name} → {self.module_type}"

    class Meta:
        verbose_name = "Módulo de evento"
        verbose_name_plural = "Módulos de evento"
        unique_together = ('event', 'module_type')


class TemplateTask(models.Model):
    """Tarea predefinida dentro de una plantilla."""
    template = models.ForeignKey(
        EventTemplate, on_delete=models.CASCADE,
        related_name='default_tasks'
    )
    title = models.CharField(max_length=200, verbose_name='Título')
    description = models.TextField(blank=True, verbose_name='Descripción')
    priority = models.CharField(
        max_length=10,
        choices=[('low', 'Baja'), ('medium', 'Media'), ('high', 'Alta')],
        default='medium',
        verbose_name='Prioridad'
    )
    days_before_event = models.IntegerField(
        null=True, blank=True,
        verbose_name='Días antes del evento',
        help_text='Fecha límite = fecha inicio − N días. Nulo = sin fecha calculada.'
    )
    order = models.IntegerField(default=0, verbose_name='Orden')

    class Meta:
        ordering = ['order']
        verbose_name = "Tarea de plantilla"
        verbose_name_plural = "Tareas de plantilla"

    def __str__(self):
        return f"{self.template.name} → {self.title}"


class TemplateChecklistItem(models.Model):
    """Ítem de checklist predefinido en una plantilla."""
    template = models.ForeignKey(
        EventTemplate, on_delete=models.CASCADE,
        related_name='default_checklist_items'
    )
    checklist_title = models.CharField(max_length=150, verbose_name='Checklist')
    item_text = models.CharField(max_length=300, verbose_name='Texto del ítem')
    order = models.IntegerField(default=0, verbose_name='Orden')

    class Meta:
        ordering = ['checklist_title', 'order']
        verbose_name = "Ítem de checklist de plantilla"
        verbose_name_plural = "Ítems de checklist de plantilla"

    def __str__(self):
        return f"{self.template.name} → {self.checklist_title}: {self.item_text}"


class TemplateBudgetItem(models.Model):
    """
    Ítem de presupuesto predefinido en una plantilla.
    Permite que al instanciar un evento desde plantilla, el presupuesto
    se pre-popule con gastos/ingresos típicos de esa categoría de evento.
    Relación: 1 EventTemplate → N TemplateBudgetItems
    """
    CATEGORY_CHOICES = [
        ('venue', 'Lugar/Espacio'),
        ('catering', 'Catering'),
        ('marketing', 'Marketing'),
        ('technology', 'Tecnología'),
        ('staff', 'Personal'),
        ('transport', 'Transporte'),
        ('other', 'Otro'),
    ]
    TYPE_CHOICES = [
        ('expense', 'Gasto'),
        ('income', 'Ingreso'),
    ]

    template = models.ForeignKey(
        EventTemplate, on_delete=models.CASCADE,
        related_name='default_budget_items'
    )
    name = models.CharField(
        max_length=200, verbose_name='Concepto',
        help_text='Descripción del gasto o ingreso estimado.'
    )
    amount_estimate = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Monto estimado',
        help_text='Valor de referencia. Puede ajustarse al crear el evento.'
    )
    item_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default='expense',
        verbose_name='Tipo'
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='other',
        verbose_name='Categoría'
    )
    order = models.IntegerField(default=0, verbose_name='Orden')

    class Meta:
        ordering = ['order']
        verbose_name = 'Ítem de presupuesto de plantilla'
        verbose_name_plural = 'Ítems de presupuesto de plantilla'

    def __str__(self):
        return f"{self.template.name} → {self.name} ({self.amount_estimate})"


class EventAlert(models.Model):
    """Alerta generada por el sistema. Es la voz del asistente."""
    ALERT_TYPE_CHOICES = [
        ('deadline', 'Fecha límite próxima'),
        ('stalled', 'Sin actividad'),
        ('budget', 'Presupuesto en riesgo'),
        ('attendance', 'Asistentes pendientes'),
        ('milestone', 'Hito importante'),
        ('suggestion', 'Sugerencia'),
        ('celebration', 'Celebración'),
    ]
    SEVERITY_CHOICES = [
        ('info', 'Información'),
        ('warning', 'Advertencia'),
        ('critical', 'Crítico'),
    ]

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='alerts'
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default='info'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    action_url = models.CharField(max_length=200, blank=True)
    action_label = models.CharField(max_length=50, blank=True)
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    alert_key = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Alerta de evento"
        verbose_name_plural = "Alertas de evento"

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class EngineMetrics(models.Model):
    """
    Registra qué decisiones tomó el engine y cómo respondió el usuario.
    Base del loop de aprendizaje.
    """
    decision_key = models.CharField(max_length=150, db_index=True)
    decision_type = models.CharField(max_length=20)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='engine_metrics'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='engine_metrics'
    )
    health_score_at_decision = models.IntegerField(default=0)
    risk_level_at_decision = models.IntegerField(default=0)

    # Respuesta del usuario: None = no respondió, True = actuó, False = descartó
    user_acted = models.BooleanField(null=True, blank=True)
    action_taken = models.CharField(max_length=50, blank=True)
    time_to_action_hours = models.FloatField(null=True, blank=True)

    issue_resolved = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Métrica del engine"
        verbose_name_plural = "Métricas del engine"
        indexes = [
            models.Index(fields=['user', 'decision_type']),
            models.Index(fields=['decision_key']),
        ]

    def __str__(self):
        return f"{self.decision_key} — {self.action_taken or 'sin respuesta'}"