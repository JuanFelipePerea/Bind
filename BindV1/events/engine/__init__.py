"""
Decision Engine — núcleo de razonamiento de BIND.
Transforma BIND de un CRUD pasivo en un asistente activo de planificación.
"""


def run_engine_for_user(user) -> dict:
    """
    Pipeline completo por usuario.
    Corre sobre todos los eventos activos y draft del usuario.
    También persiste alertas via alert_engine (idempotente).

    Retorna:
    {
        'event_scores': {event_id: EventScore},
        'event_contexts': {event_id: EventContext},
        'all_decisions': [Decision, ...] ordenadas por severidad (critical first),
        'dashboard_summary': {
            'critical_count': int,
            'events_at_risk': int,
            'events_on_track': int,
            'needs_attention': bool,
        }
    }
    """
    from events.models import Event
    from events.engine.context import build_event_context
    from events.engine.scorer import score_event
    from events.engine.decisions import derive_decisions

    events = Event.objects.filter(
        owner=user,
        status__in=['active', 'draft']
    ).prefetch_related('tasks', 'attendees', 'modules')

    event_scores = {}
    event_contexts = {}
    all_decisions = []

    for event in events:
        ctx = build_event_context(event)
        score = score_event(ctx)
        decisions = derive_decisions(ctx, score)

        event_scores[event.pk] = score
        event_contexts[event.pk] = ctx
        all_decisions.extend(decisions)

    # Ordenar: critical primero, luego warning, luego info
    severity_order = {'critical': 0, 'warning': 1, 'info': 2}
    all_decisions.sort(key=lambda d: severity_order.get(d.severity, 99))

    # Persistir alertas via alert_engine (get_or_create → idempotente)
    try:
        from events.services.alert_engine import run_alert_engine
        run_alert_engine(user)
    except Exception:
        pass

    return {
        'event_scores': event_scores,
        'event_contexts': event_contexts,
        'all_decisions': all_decisions[:5],
        'dashboard_summary': _build_summary(event_scores, all_decisions),
    }


def _build_summary(scores: dict, decisions: list) -> dict:
    critical_count = sum(1 for d in decisions if d.severity == 'critical')
    at_risk = sum(
        1 for s in scores.values()
        if s.risk_label in ('critical', 'high')
    )
    on_track = sum(
        1 for s in scores.values()
        if s.health_label in ('excellent', 'good')
    )
    return {
        'critical_count': critical_count,
        'events_at_risk': at_risk,
        'events_on_track': on_track,
        'needs_attention': critical_count > 0 or at_risk > 0,
    }
