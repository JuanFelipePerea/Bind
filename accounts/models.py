from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator


class UserProfile(models.Model):
    """
    Extiende el User de Django con campos adicionales de BIND.
    Se crea automáticamente al registrar un usuario.
    Relación: 1 User → 1 UserProfile (OneToOne)
    """

    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('organizer', 'Organizador'),
        ('collaborator', 'Colaborador'),
    ]

    # Enlace al User de Django (si se borra el User, se borra el perfil)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Rol del usuario dentro de BIND
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='organizer')

    # Foto de perfil
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Teléfono/celular — E.164 máx 16 chars (+[hasta 15 dígitos])
    _phone_validator = RegexValidator(
        regex=r'^\+?\d{7,15}$',
        message='Ingresa un número válido: entre 7 y 15 dígitos, opcionalmente con + al inicio. '
                'Colombia: +57 seguido de 10 dígitos (ej. +573001234567).',
    )
    phone = models.CharField(max_length=16, blank=True, null=True, validators=[_phone_validator])

    # Descripción/bio
    bio = models.TextField(max_length=500, blank=True, null=True)

    # Verificación en 2 pasos
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)
    two_factor_sent_at = models.DateTimeField(null=True, blank=True)

    # Fecha de creación del perfil
    created_at = models.DateTimeField(auto_now_add=True)

    # Tutorial de onboarding
    onboarding_completed = models.BooleanField(default=False)

    @property
    def google_calendar_connected(self):
        """True si el usuario tiene un refresh_token de Google con scope de Calendar."""
        from allauth.socialaccount.models import SocialToken
        return SocialToken.objects.filter(
            account__user=self.user,
            account__provider='google',
            token_secret__isnull=False,
        ).exclude(token_secret='').exists()

    @property
    def google_refresh_token(self):
        """Retorna el refresh_token de Google, o None si no existe."""
        from allauth.socialaccount.models import SocialToken
        token = SocialToken.objects.filter(
            account__user=self.user,
            account__provider='google',
            token_secret__isnull=False,
        ).exclude(token_secret='').first()
        return token.token_secret if token else None

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"


@receiver(post_save, sender=User)
def auto_create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


class EmailTemplate(models.Model):
    """Plantillas de email personalizables por usuario."""

    TYPE_CHOICES = [
        ('invitation', '🎟 Invitación a evento'),
        ('welcome',    '🎉 Bienvenida'),
        ('digest',     '🤖 Resumen semanal (Bynix)'),
        ('alert',      '🚨 Alertas del sistema'),
    ]

    DEFAULT_SUBJECTS = {
        'invitation': 'Invitación: {event}',
        'welcome':    'Bienvenido a BIND',
        'digest':     'Bynix · Tu semana en BIND',
        'alert':      'Atención requerida en BIND',
    }

    DEFAULT_BODIES = {
        'invitation': (
            'Te esperamos en este evento especial. '
            'Confirma tu asistencia usando el botón de abajo.'
        ),
        'welcome': (
            'Nos alegra tenerte en BIND. '
            'Empieza creando tu primer evento y deja que Bynix te ayude a gestionarlo.'
        ),
        'digest': (
            'Aquí tienes el resumen semanal de tus eventos. '
            'Revisa las recomendaciones de Bynix para mantener todo en orden.'
        ),
        'alert': (
            'Bynix detectó situaciones que requieren tu atención. '
            'Revisa los detalles a continuación.'
        ),
    }

    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_templates')
    email_type   = models.CharField(max_length=20, choices=TYPE_CHOICES)
    custom_subject = models.CharField(max_length=200, blank=True,
                                      help_text='Deja vacío para usar el asunto por defecto.')
    custom_body  = models.TextField(blank=True,
                                    help_text='Mensaje que aparece en el cuerpo del email.')
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'email_type')
        verbose_name = 'Plantilla de email'
        verbose_name_plural = 'Plantillas de email'

    def get_subject(self, **kwargs):
        """Retorna el asunto final (personalizado o por defecto)."""
        if self.custom_subject:
            return self.custom_subject.format(**kwargs)
        tpl = self.DEFAULT_SUBJECTS.get(self.email_type, '')
        return tpl.format(**kwargs)

    def get_body(self):
        """Retorna el cuerpo personalizado o el por defecto."""
        return self.custom_body or self.DEFAULT_BODIES.get(self.email_type, '')

    def __str__(self):
        return f"{self.user.username} · {self.get_email_type_display()}"