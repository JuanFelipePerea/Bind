from django.db.models import Count, Q


def alert_counts(request):
    if not request.user.is_authenticated:
        return {
            'alert_badge_count': 0,
            'alert_badge_critical': 0,
            'alert_badge_warning': 0,
        }
    try:
        from events.models import EventAlert
        counts = EventAlert.objects.filter(
            event__owner=request.user,
            is_dismissed=False,
            is_read=False,
        ).aggregate(
            total=Count('id'),
            critical=Count('id', filter=Q(severity='critical')),
            warning=Count('id', filter=Q(severity='warning')),
        )
        return {
            'alert_badge_count': counts['total'] or 0,
            'alert_badge_critical': counts['critical'] or 0,
            'alert_badge_warning': counts['warning'] or 0,
        }
    except Exception:
        return {
            'alert_badge_count': 0,
            'alert_badge_critical': 0,
            'alert_badge_warning': 0,
        }
