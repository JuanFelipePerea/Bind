"""
Dispatcher — orquesta el pipeline completo del Decision Engine.

Flujo:
  Event → build_event_context() → score_event() → derive_decisions()
        → persist_alerts() → return results

El Dispatcher es el único punto de entrada externo al engine.
Las vistas y servicios llaman dispatch_for_event() o dispatch_for_user().
"""

from events.engine.context import build_event_context
from events.engine.scorer import score_event
from events.engine.decisions import derive_decisions


def dispatch_for_event(event):
    """
    Ejecuta el pipeline completo del engine para un evento específico.
    Retorna dict con context, score y decisions.
    """
    ctx = build_event_context(event)
    score = score_event(ctx)
    decisions = derive_decisions(ctx, score)
    return {
        'context': ctx,
        'score': score,
        'decisions': decisions,
    }


def dispatch_for_user(user):
    """
    Ejecuta el pipeline para todos los eventos activos/borrador del usuario.
    Retorna lista de resultados ordenados por score descendente.
    """
    from events.models import Event
    events = Event.objects.filter(
        owner=user, status__in=['active', 'draft']
    ).prefetch_related('tasks', 'attendees')

    results = []
    for event in events:
        result = dispatch_for_event(event)
        result['event'] = event
        results.append(result)

    results.sort(key=lambda r: r['score'].risk_level, reverse=True)
    return results
