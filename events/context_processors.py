"""
Context processor global de BIND.
Inyecta créditos de Bynix y alertas activas del motor en todos los templates.
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
            'global_alerts': [],
            'global_alerts_count': 0,
        }

    credits = get_user_credits(request.user.pk)
    usage = get_usage_percent(request.user.pk)
    reset_info = get_credits_reset_info(request.user.pk)

    try:
        from events.models import EventAlert
        global_alerts = list(
            EventAlert.objects.filter(
                event__owner=request.user,
                is_dismissed=False,
            ).select_related('event').order_by('-created_at')[:15]
        )
    except Exception:
        global_alerts = []

    return {
        'bynix_credits': credits,
        'bynix_credits_max': BYNIX_DAILY_CREDITS,
        'bynix_usage_percent': usage,
        'bynix_reset_time': reset_info['reset_time'],
        'global_alerts': global_alerts,
        'global_alerts_count': len(global_alerts),
    }
