"""
Scorer — asigna un puntaje de riesgo/urgencia a un EventContext.

Escala: 0 (sin riesgo) → 100 (crítico).
El score se usa para priorizar qué eventos aparecen primero en el dashboard
y para determinar la severidad de las alertas generadas.
"""

from events.engine.context import EventContext


class EventScore:
    """Resultado del scoring: encapsula risk_level y deriva etiquetas."""

    def __init__(self, risk_level: int, momentum: str = 'stable'):
        self.risk_level = min(max(risk_level, 0), 100)
        self._momentum = momentum

    @property
    def health_score(self) -> int:
        return max(0, 100 - self.risk_level)

    @property
    def health_label(self) -> str:
        h = self.health_score
        if h >= 80:
            return 'excellent'
        if h >= 60:
            return 'good'
        if h >= 40:
            return 'at_risk'
        return 'critical'

    @property
    def risk_label(self) -> str:
        if self.risk_level >= 70:
            return 'critical'
        if self.risk_level >= 50:
            return 'high'
        if self.risk_level >= 30:
            return 'medium'
        return 'low'

    @property
    def momentum_label(self) -> str:
        return self._momentum

    def __repr__(self):
        return (
            f"EventScore(risk={self.risk_level}, health={self.health_score}, "
            f"label={self.health_label})"
        )


def score_event(ctx: EventContext) -> EventScore:
    """
    Calcula el puntaje de urgencia de un evento dado su contexto.
    Retorna un EventScore con health_score, health_label, risk_label,
    momentum_label.
    """
    score = 0

    if ctx.days_until is not None:
        if ctx.days_until <= 3:
            score += 40
        elif ctx.days_until <= 7:
            score += 25
        elif ctx.days_until <= 14:
            score += 10
        elif ctx.days_until <= 30:
            score += 5

    if ctx.task_high_pending > 0 and ctx.days_until is not None and ctx.days_until <= 7:
        score += 30

    pending_ratio = (ctx.task_pending / ctx.task_total) if ctx.task_total > 0 else 0
    if pending_ratio > 0.5 and ctx.days_until is not None and ctx.days_until <= 7:
        score += 20

    if ctx.task_overdue >= 3:
        score += 15
    elif ctx.task_overdue >= 1:
        score += 8

    if ctx.last_activity_days is not None and ctx.last_activity_days >= 7:
        if ctx.days_until is not None and ctx.days_until <= 30:
            score += 10

    if ctx.attendee_pending > 0 and ctx.days_until is not None and ctx.days_until <= 7:
        score += 5

    risk_level = min(score, 100)

    # Determinar momentum basado en actividad y progreso
    if ctx.last_activity_days is not None and ctx.last_activity_days <= 2 and ctx.progress_pct >= 50:
        momentum = 'accelerating'
    elif ctx.last_activity_days is not None and ctx.last_activity_days > 14:
        momentum = 'stalled'
    elif ctx.last_activity_days is not None and ctx.last_activity_days > 7:
        momentum = 'slowing'
    else:
        momentum = 'stable'

    return EventScore(risk_level=risk_level, momentum=momentum)
