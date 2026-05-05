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

    # Fecha de creación del perfil
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"


@receiver(post_save, sender=User)
def auto_create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)