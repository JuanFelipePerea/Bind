"""
Context processor global de Bynix.
Inyecta el estado de créditos en todos los templates de forma automática.
"""

from events.services.ai_service import (
    get_user_credits,
    get_usage_percent,
    get_credits_reset_info,
    BYNIX_DAILY_CREDITS,
)


def bynix_credits(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'bynix_credits': BYNIX_DAILY_CREDITS,
            'bynix_credits_max': BYNIX_DAILY_CREDITS,
            'bynix_usage_percent': 0,
            'bynix_reset_time': 'mañana',
        }

    credits = get_user_credits(request.user.pk)
    usage = get_usage_percent(request.user.pk)
    reset_info = get_credits_reset_info(request.user.pk)
    return {
        'bynix_credits': credits,
        'bynix_credits_max': BYNIX_DAILY_CREDITS,
        'bynix_usage_percent': usage,
        'bynix_reset_time': reset_info['reset_time'],
    }
