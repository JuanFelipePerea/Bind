from django.conf import settings
from django.contrib.auth.models import User
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


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
            existing_user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return

        # Conecta el SocialAccount al User existente y continúa la sesión.
        # Esto evita el bucle a /3rdparty/signup/ cuando el email ya está
        # registrado manualmente.
        sociallogin.connect(request, existing_user)

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        from accounts.models import UserProfile
        UserProfile.objects.get_or_create(user=user)
        return user

    def is_open_for_signup(self, request, sociallogin):
        return True
