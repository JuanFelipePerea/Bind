import uuid

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from cloudinary_storage.storage import RawMediaCloudinaryStorage
from events.models import Event

# ─── Monedas del mundo (ISO 4217) ─────────────────────────────────────────────
CURRENCY_CHOICES = [
    # Más usadas primero
    ('USD', 'USD — Dólar estadounidense'),
    ('EUR', 'EUR — Euro'),
    ('COP', 'COP — Peso colombiano'),
    ('MXN', 'MXN — Peso mexicano'),
    ('ARS', 'ARS — Peso argentino'),
    ('CLP', 'CLP — Peso chileno'),
    ('PEN', 'PEN — Sol peruano'),
    ('BRL', 'BRL — Real brasileño'),
    ('GBP', 'GBP — Libra esterlina'),
    ('JPY', 'JPY — Yen japonés'),
    ('CAD', 'CAD — Dólar canadiense'),
    ('AUD', 'AUD — Dólar australiano'),
    ('CHF', 'CHF — Franco suizo'),
    ('CNY', 'CNY — Yuan chino'),
    ('INR', 'INR — Rupia india'),
    # Resto alfabético
    ('AED', 'AED — Dírham de EAU'),
    ('AFN', 'AFN — Afgani afgano'),
    ('ALL', 'ALL — Lek albanés'),
    ('AMD', 'AMD — Dram armenio'),
    ('ANG', 'ANG — Florín antillano'),
    ('AOA', 'AOA — Kwanza angoleño'),
    ('AWG', 'AWG — Florín arubeño'),
    ('AZN', 'AZN — Manat azerbaiyano'),
    ('BAM', 'BAM — Marco bosnio'),
    ('BBD', 'BBD — Dólar de Barbados'),
    ('BDT', 'BDT — Taka bangladesí'),
    ('BGN', 'BGN — Lev búlgaro'),
    ('BHD', 'BHD — Dinar bareiní'),
    ('BIF', 'BIF — Franco burundés'),
    ('BMD', 'BMD — Dólar de Bermudas'),
    ('BND', 'BND — Dólar de Brunéi'),
    ('BOB', 'BOB — Boliviano'),
    ('BSD', 'BSD — Dólar bahameño'),
    ('BTN', 'BTN — Ngultrum butanés'),
    ('BWP', 'BWP — Pula botsuanesa'),
    ('BYN', 'BYN — Rublo bielorruso'),
    ('BZD', 'BZD — Dólar de Belice'),
    ('CDF', 'CDF — Franco congoleño'),
    ('CRC', 'CRC — Colón costarricense'),
    ('CUP', 'CUP — Peso cubano'),
    ('CVE', 'CVE — Escudo caboverdiano'),
    ('CZK', 'CZK — Corona checa'),
    ('DJF', 'DJF — Franco yibutiano'),
    ('DKK', 'DKK — Corona danesa'),
    ('DOP', 'DOP — Peso dominicano'),
    ('DZD', 'DZD — Dinar argelino'),
    ('EGP', 'EGP — Libra egipcia'),
    ('ERN', 'ERN — Nakfa eritreo'),
    ('ETB', 'ETB — Birr etíope'),
    ('FJD', 'FJD — Dólar fiyiano'),
    ('FKP', 'FKP — Libra malvinense'),
    ('GEL', 'GEL — Lari georgiano'),
    ('GHS', 'GHS — Cedi ghanés'),
    ('GIP', 'GIP — Libra gibraltareña'),
    ('GMD', 'GMD — Dalasi gambiano'),
    ('GNF', 'GNF — Franco guineano'),
    ('GTQ', 'GTQ — Quetzal guatemalteco'),
    ('GYD', 'GYD — Dólar guyanés'),
    ('HKD', 'HKD — Dólar de Hong Kong'),
    ('HNL', 'HNL — Lempira hondureño'),
    ('HRK', 'HRK — Kuna croata'),
    ('HTG', 'HTG — Gourde haitiano'),
    ('HUF', 'HUF — Forinto húngaro'),
    ('IDR', 'IDR — Rupia indonesia'),
    ('ILS', 'ILS — Nuevo séquel israelí'),
    ('IQD', 'IQD — Dinar iraquí'),
    ('IRR', 'IRR — Rial iraní'),
    ('ISK', 'ISK — Corona islandesa'),
    ('JMD', 'JMD — Dólar jamaicano'),
    ('JOD', 'JOD — Dinar jordano'),
    ('KES', 'KES — Chelín keniano'),
    ('KGS', 'KGS — Som kirguís'),
    ('KHR', 'KHR — Riel camboyano'),
    ('KMF', 'KMF — Franco comorense'),
    ('KPW', 'KPW — Won norcoreano'),
    ('KRW', 'KRW — Won surcoreano'),
    ('KWD', 'KWD — Dinar kuwaití'),
    ('KYD', 'KYD — Dólar de Caimán'),
    ('KZT', 'KZT — Tenge kazajo'),
    ('LAK', 'LAK — Kip laosiano'),
    ('LBP', 'LBP — Libra libanesa'),
    ('LKR', 'LKR — Rupia de Sri Lanka'),
    ('LRD', 'LRD — Dólar liberiano'),
    ('LSL', 'LSL — Loti lesotense'),
    ('LYD', 'LYD — Dinar libio'),
    ('MAD', 'MAD — Dírham marroquí'),
    ('MDL', 'MDL — Leu moldavo'),
    ('MGA', 'MGA — Ariary malgache'),
    ('MKD', 'MKD — Denar macedonio'),
    ('MMK', 'MMK — Kyat birmano'),
    ('MNT', 'MNT — Tugrik mongol'),
    ('MOP', 'MOP — Pataca macaense'),
    ('MRU', 'MRU — Uguiya mauritana'),
    ('MUR', 'MUR — Rupia mauriciana'),
    ('MVR', 'MVR — Rufiyaa maldiva'),
    ('MWK', 'MWK — Kwacha malauí'),
    ('MYR', 'MYR — Ringgit malayo'),
    ('MZN', 'MZN — Metical mozambiqueño'),
    ('NAD', 'NAD — Dólar namibio'),
    ('NGN', 'NGN — Naira nigeriana'),
    ('NIO', 'NIO — Córdoba nicaragüense'),
    ('NOK', 'NOK — Corona noruega'),
    ('NPR', 'NPR — Rupia nepalesa'),
    ('NZD', 'NZD — Dólar neozelandés'),
    ('OMR', 'OMR — Rial omaní'),
    ('PAB', 'PAB — Balboa panameño'),
    ('PHP', 'PHP — Peso filipino'),
    ('PKR', 'PKR — Rupia pakistaní'),
    ('PLN', 'PLN — Esloti polaco'),
    ('PYG', 'PYG — Guaraní paraguayo'),
    ('QAR', 'QAR — Riyal catarí'),
    ('RON', 'RON — Leu rumano'),
    ('RSD', 'RSD — Dinar serbio'),
    ('RUB', 'RUB — Rublo ruso'),
    ('RWF', 'RWF — Franco ruandés'),
    ('SAR', 'SAR — Riyal saudí'),
    ('SBD', 'SBD — Dólar de Salomón'),
    ('SCR', 'SCR — Rupia de Seychelles'),
    ('SDG', 'SDG — Libra sudanesa'),
    ('SEK', 'SEK — Corona sueca'),
    ('SGD', 'SGD — Dólar de Singapur'),
    ('SHP', 'SHP — Libra de Santa Elena'),
    ('SLL', 'SLL — Leone de Sierra Leona'),
    ('SOS', 'SOS — Chelín somalí'),
    ('SRD', 'SRD — Dólar surinamés'),
    ('STN', 'STN — Dobra de Santo Tomé'),
    ('SVC', 'SVC — Colón salvadoreño'),
    ('SYP', 'SYP — Libra siria'),
    ('SZL', 'SZL — Lilangeni suazi'),
    ('THB', 'THB — Baht tailandés'),
    ('TJS', 'TJS — Somoni tayiko'),
    ('TMT', 'TMT — Manat turcomano'),
    ('TND', 'TND — Dinar tunecino'),
    ('TOP', 'TOP — Paʻanga tongano'),
    ('TRY', 'TRY — Lira turca'),
    ('TTD', 'TTD — Dólar de Trinidad'),
    ('TWD', 'TWD — Nuevo dólar taiwanés'),
    ('TZS', 'TZS — Chelín tanzano'),
    ('UAH', 'UAH — Hryvnia ucraniana'),
    ('UGX', 'UGX — Chelín ugandés'),
    ('UYU', 'UYU — Peso uruguayo'),
    ('UZS', 'UZS — Som uzbeko'),
    ('VES', 'VES — Bolívar venezolano'),
    ('VND', 'VND — Dong vietnamita'),
    ('VUV', 'VUV — Vatu vanuatense'),
    ('WST', 'WST — Tālā samoano'),
    ('XAF', 'XAF — Franco CFA central'),
    ('XCD', 'XCD — Dólar del Caribe'),
    ('XOF', 'XOF — Franco CFA occidental'),
    ('XPF', 'XPF — Franco CFP'),
    ('YER', 'YER — Rial yemení'),
    ('ZAR', 'ZAR — Rand sudafricano'),
    ('ZMW', 'ZMW — Kwacha zambiano'),
    ('ZWL', 'ZWL — Dólar zimbabuense'),
]

# Límites de monto para evitar valores absurdos
BUDGET_MAX_AMOUNT = 999_999_999   # ~1 billón
ITEM_MAX_AMOUNT   = 999_999_999


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
    title = models.CharField(
        max_length=200, verbose_name='Título',
        help_text='Nombre descriptivo de la actividad a realizar.'
    )
    description = models.TextField(blank=True, verbose_name='Descripción')
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default='medium',
        verbose_name='Prioridad'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name='Estado'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tasks',
        verbose_name='Responsable',
        help_text='Usuario interno responsable de completar esta tarea.'
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='Fecha límite')
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
    name = models.CharField(max_length=150, verbose_name='Nombre completo')
    email = models.EmailField(blank=True, verbose_name='Correo electrónico')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name='Estado de asistencia'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendances',
        verbose_name='Usuario BIND',
        help_text='Cuenta BIND del asistente. Dejar vacío para invitados externos.'
    )

    invitation_token   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    token_expires_at   = models.DateTimeField(null=True, blank=True)
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
    """Archivo adjunto a un evento. Relación: 1 Event → N Files."""

    FILE_TYPE_CHOICES = [
        ('image', 'Imagen'),
        ('document', 'Documento'),
        ('spreadsheet', 'Hoja de cálculo'),
        ('pdf', 'PDF'),
        ('other', 'Otro'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='files')
    name = models.CharField(max_length=200)

    file = models.FileField(
        upload_to='event_files/%Y/%m/',
        blank=True,
        null=True,
        storage=RawMediaCloudinaryStorage(),
        verbose_name='Archivo',
    )
    file_path = models.CharField(max_length=500, blank=True)  # legado

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


class Budget(models.Model):
    """Presupuesto por evento. Relación: 1 Event → 1 Budget."""
    event = models.OneToOneField(
        Event, on_delete=models.CASCADE, related_name='budget'
    )
    total_budget = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Presupuesto total',
        help_text='Monto máximo autorizado para el evento.',
        validators=[
            MinValueValidator(0),
            MaxValueValidator(BUDGET_MAX_AMOUNT),
        ]
    )
    currency = models.CharField(
        max_length=3, default='COP',
        choices=CURRENCY_CHOICES,
        verbose_name='Moneda',
        help_text='Código ISO 4217 (COP, USD, EUR…).'
    )
    notes = models.TextField(blank=True, verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_spent(self):
        from django.db.models import Sum
        return self.items.aggregate(total=Sum('amount'))['total'] or 0

    @property
    def remaining(self):
        return self.total_budget - self.total_spent

    @property
    def usage_percentage(self):
        if self.total_budget == 0:
            return 0
        return int((self.total_spent / self.total_budget) * 100)

    def __str__(self):
        return f"Presupuesto: {self.event.name}"

    class Meta:
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"


class BudgetItem(models.Model):
    """Gasto o ingreso individual dentro del presupuesto."""
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

    budget = models.ForeignKey(
        Budget, on_delete=models.CASCADE, related_name='items'
    )
    name = models.CharField(
        max_length=200, verbose_name='Concepto',
        help_text='Descripción del gasto o ingreso.'
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name='Monto',
        validators=[
            MinValueValidator(0),
            MaxValueValidator(ITEM_MAX_AMOUNT),
        ]
    )
    item_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default='expense',
        verbose_name='Tipo'
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='other',
        verbose_name='Categoría'
    )
    related_task = models.ForeignKey(
        'Task', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='budget_items',
        verbose_name='Tarea asociada',
        help_text='Tarea del evento a la que corresponde este ítem. Facilita la trazabilidad costo-actividad.'
    )
    paid = models.BooleanField(
        default=False, verbose_name='Pagado',
        help_text='Marca este ítem como liquidado.'
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='Fecha de pago')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — {self.amount} {self.budget.currency}"

    class Meta:
        verbose_name = "Ítem de presupuesto"
        verbose_name_plural = "Ítems de presupuesto"
        ordering = ['-created_at']


class AttendeePreference(models.Model):
    """Preferencias del invitado, capturadas vía portal público."""

    DIETARY_CHOICES = [
        ('none',        'Sin restricciones'),
        ('vegetarian',  'Vegetariano'),
        ('vegan',       'Vegano'),
        ('gluten_free', 'Sin gluten'),
        ('halal',       'Halal'),
        ('kosher',      'Kosher'),
        ('other',       'Otro'),
    ]

    attendee      = models.OneToOneField(
        Attendee, on_delete=models.CASCADE,
        related_name='preference', verbose_name='Asistente'
    )
    dietary       = models.CharField(
        max_length=20, choices=DIETARY_CHOICES, default='none',
        verbose_name='Restricción alimentaria'
    )
    accessibility = models.BooleanField(
        default=False, verbose_name='Necesidades de accesibilidad'
    )
    notes         = models.TextField(blank=True, verbose_name='Notas adicionales')
    responded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Preferencia de asistente"
        verbose_name_plural = "Preferencias de asistentes"

    def __str__(self):
        return f"Preferencia de {self.attendee.name}"