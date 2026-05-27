"""
Utilidades para envío de emails HTML con plantillas BIND.

Uso:
    from events.email_utils import send_bind_email

    send_bind_email(
        template_name='bienvenida',   # nombre sin extensión bajo templates/emails/
        subject='¡Bienvenido a BIND!',
        recipient=user.email,
        context={'nombre': user.first_name, ...},
    )
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://bind.onrender.com').rstrip('/')


def send_bind_email(
    template_name: str,
    subject: str,
    recipient: str | list[str],
    context: dict | None = None,
    attachments: list | None = None,
    fail_silently: bool = False,
) -> bool:
    """
    Renderiza templates/emails/<template_name>.html y lo envía como email HTML
    con fallback de texto plano.

    Returns:
        True si se envió correctamente, False si hubo error.
    """
    ctx = {'site_url': SITE_URL, **(context or {})}

    try:
        html_content = render_to_string(f'emails/{template_name}.html', ctx)
        text_content = strip_tags(html_content)

        recipients = [recipient] if isinstance(recipient, str) else recipient

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        msg.attach_alternative(html_content, 'text/html')

        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)

        msg.send(fail_silently=fail_silently)
        return True

    except Exception as exc:
        logger.error('Error enviando email "%s" a %s: %s', template_name, recipient, exc)
        if not fail_silently:
            raise
        return False
