import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from events.email_utils import send_bind_email

logger = logging.getLogger(__name__)


class BindSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adaptador social de BIND.

    Responsabilidades:
    1. pre_social_login  – si el email de Google ya existe en la BD, conecta
                           el SocialAccount al User existente y lo autentica
                           directamente, sin pasar por /3rdparty/signup/.
    2. save_user         – garantiza que UserProfile se crea con get_or_create
                           (defensa secundaria frente al signal post_save).
    3. is_open_for_signup – siempre permite nuevo registro social.
    """

    def pre_social_login(self, request, sociallogin):
        # Si la cuenta social ya existe en la BD, no hay nada que resolver.
        if sociallogin.is_existing:
            return

        email = (sociallogin.account.extra_data.get('email') or '').strip().lower()
        if not email:
            return

        try:
            # Usar filter().first() en lugar de get() para evitar
            # MultipleObjectsReturned cuando varios usuarios comparten email.
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user is None:
                return

            # Conecta el SocialAccount al User existente y continúa la sesión.
            # Esto evita el bucle a /3rdparty/signup/ cuando el email ya está
            # registrado manualmente.
            sociallogin.connect(request, existing_user)

        except Exception as exc:
            # Loguear sin propagar: un fallo aquí no debe bloquear el login.
            logger.exception("pre_social_login error para email=%s: %s", email, exc)

    def save_user(self, request, sociallogin, form=None):
        try:
            user = super().save_user(request, sociallogin, form)
        except Exception as exc:
            logger.exception("save_user falló en BindSocialAccountAdapter: %s", exc)
            raise  # re-raise: allauth necesita este error para manejar el flujo

        from accounts.models import UserProfile
        UserProfile.objects.get_or_create(user=user)

        if user.email:
            name = user.first_name or user.username
            from accounts.models import EmailTemplate
            welcome_tpl = EmailTemplate.objects.filter(user=user, email_type='welcome').first()
            subject = welcome_tpl.get_subject() if (welcome_tpl and welcome_tpl.custom_subject) else '¡Bienvenido a BIND! 🎉'
            custom_message = welcome_tpl.get_body() if welcome_tpl else ''
            send_bind_email(
                template_name='bienvenida',
                subject=subject,
                recipient=user.email,
                context={'nombre': name, 'via_google': True, 'custom_message': custom_message},
                fail_silently=True,
            )

        return user

    def is_open_for_signup(self, request, sociallogin):
        return True
