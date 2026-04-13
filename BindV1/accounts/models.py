from django.db import models
from django.contrib.auth.models import User


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

    # Teléfono/celular
    phone = models.CharField(max_length=20, blank=True, null=True)

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