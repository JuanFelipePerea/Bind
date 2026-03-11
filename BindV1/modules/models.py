from django.db import models
from django.contrib.auth.models import User
from events.models import Event


class Task(models.Model):
    """
    Tarea asignada dentro de un evento.
    Relación: 1 Event → N Tasks
    Relación: 1 User → N Tasks (assigned_to puede ser nulo)
    """

    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En progreso'),
        ('done', 'Completada'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # A quién está asignada la tarea (puede no estar asignada aún)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )

    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.event.name}] {self.title}"

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ['-created_at']


class Attendee(models.Model):
    """
    Invitado o participante de un evento.
    NO necesita tener cuenta en BIND — puede ser solo nombre + email.
    Si tiene cuenta, se vincula opcionalmente al User del sistema.
    Relación: 1 Event → N Attendees
    """

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('confirmed', 'Confirmado'),
        ('declined', 'Rechazado'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendees')
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Enlace opcional al User de Django (null si es invitado externo sin cuenta)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendances'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} → {self.event.name}"

    class Meta:
        verbose_name = "Asistente"
        verbose_name_plural = "Asistentes"


class Checklist(models.Model):
    """
    Lista de verificación dentro de un evento.
    Un evento puede tener múltiples Checklists independientes.
    Relación: 1 Event → N Checklists
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='checklists')
    title = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.event.name})"

    def progress(self):
        """
        Calcula el progreso como porcentaje: items marcados / total items.
        Retorna 0 si no hay items.
        """
        total = self.items.count()
        if total == 0:
            return 0
        checked = self.items.filter(is_checked=True).count()
        return int((checked / total) * 100)

    class Meta:
        verbose_name = "Checklist"
        verbose_name_plural = "Checklists"


class ChecklistItem(models.Model):
    """
    Ítem individual dentro de una Checklist.
    Relación: 1 Checklist → N ChecklistItems
    Al eliminar la Checklist, se eliminan sus ítems (CASCADE).
    """

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='items')
    text = models.CharField(max_length=300)
    is_checked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "✓" if self.is_checked else "○"
        return f"{status} {self.text}"

    class Meta:
        verbose_name = "Ítem de checklist"
        verbose_name_plural = "Ítems de checklist"


class File(models.Model):
    """
    Archivo adjunto a un evento.
    MVP: se guarda solo la ruta como string (no FileField real).
    Se puede escalar a FileField + Pillow en fases futuras.
    Relación: 1 Event → N Files
    """

    FILE_TYPE_CHOICES = [
        ('image', 'Imagen'),
        ('document', 'Documento'),
        ('spreadsheet', 'Hoja de cálculo'),
        ('pdf', 'PDF'),
        ('other', 'Otro'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='files')
    name = models.CharField(max_length=200)

    # Ruta del archivo (string simple en MVP)
    file_path = models.CharField(max_length=500)

    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')

    # Quién subió el archivo (útil para auditoría futura)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_files'
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.event.name})"

    class Meta:
        verbose_name = "Archivo"
        verbose_name_plural = "Archivos"
        ordering = ['-uploaded_at']