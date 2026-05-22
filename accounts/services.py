"""
Servicios de integración con APIs de Google para BIND.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_google_calendar_service(user):
    """
    Construye y retorna un servicio autenticado de Google Calendar API.
    Retorna None si el usuario no tiene tokens válidos o si la librería no está disponible.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from allauth.socialaccount.models import SocialToken
    except ImportError:
        logger.warning("google-api-python-client no instalado — Google Calendar sync deshabilitado.")
        return None

    token_obj = SocialToken.objects.filter(
        account__user=user,
        account__provider='google',
        token_secret__isnull=False,
    ).exclude(token_secret='').first()

    if not token_obj:
        return None

    provider_settings = settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {})
    creds = Credentials(
        token=token_obj.token,
        refresh_token=token_obj.token_secret,
        client_id=provider_settings.get('client_id', ''),
        client_secret=provider_settings.get('secret', ''),
        token_uri='https://oauth2.googleapis.com/token',
    )

    try:
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Error construyendo Google Calendar service para {user.username}: {e}")
        return None


def push_event_to_google_calendar(event, user):
    """
    Crea o actualiza el evento en Google Calendar del usuario.
    Silencia errores — si falla, el evento en BIND igualmente se guarda.
    Retorna el google_event_id si tuvo éxito, None si falló.
    """
    if not event.start_date or not event.end_date:
        return None

    service = get_google_calendar_service(user)
    if not service:
        return None

    from django.utils.timezone import localtime
    start_local = localtime(event.start_date)
    end_local   = localtime(event.end_date)

    _site = getattr(settings, 'SITE_URL', '').rstrip('/')
    _event_url = f"{_site}/events/{event.pk}/" if _site else ''

    body = {
        'summary':     event.name,
        'description': event.description or '',
        'location':    event.location or '',
        'start': {
            'dateTime': start_local.isoformat(),
            'timeZone': 'America/Bogota',
        },
        'end': {
            'dateTime': end_local.isoformat(),
            'timeZone': 'America/Bogota',
        },
        'source': {
            'title': 'BIND',
            'url':   _event_url,
        },
    }

    try:
        result = service.events().insert(calendarId='primary', body=body).execute()
        google_id = result.get('id')
        logger.info(f"Evento '{event.name}' (pk={event.pk}) sincronizado con Google Calendar (gid={google_id})")
        return google_id
    except Exception as e:
        logger.warning(f"No se pudo sincronizar '{event.name}' con Google Calendar: {e}")
        return None
