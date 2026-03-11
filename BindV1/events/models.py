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

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='business')

    # Color representativo de la tarjeta (hex string, ej: "#3B82F6")
    color = models.CharField(max_length=7, default='#3B82F6')

    # El creador de la plantilla
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='templates')
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
    Ej: la plantilla "Boda" incluye módulos: tasks, attendees, checklist, files.
    Relación: 1 EventTemplate → N TemplateModules
    """

    MODULE_CHOICES = [
        ('tasks', 'Tareas'),
        ('attendees', 'Asistentes'),
        ('checklist', 'Checklist'),
        ('files', 'Archivos'),
    ]

    template = models.ForeignKey(EventTemplate, on_delete=models.CASCADE, related_name='modules')
    module_type = models.CharField(max_length=20, choices=MODULE_CHOICES)

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

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Fechas del evento
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # El usuario que creó/posee el evento
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')

    # Plantilla base (opcional — un evento puede crearse desde cero)
    template = models.ForeignKey(
        EventTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events'
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
    Ej: el evento "Boda Ana & Luis" tiene activos: tasks, attendees, checklist.
    Relación: 1 Event → N EventModules
    """

    MODULE_CHOICES = [
        ('tasks', 'Tareas'),
        ('attendees', 'Asistentes'),
        ('checklist', 'Checklist'),
        ('files', 'Archivos'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='modules')
    module_type = models.CharField(max_length=20, choices=MODULE_CHOICES)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.event.name} → {self.module_type}"

    class Meta:
        verbose_name = "Módulo de evento"
        verbose_name_plural = "Módulos de evento"
        unique_together = ('event', 'module_type')