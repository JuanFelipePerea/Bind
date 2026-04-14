"""
Learning — módulo de aprendizaje y mejora continua del engine.

Responsabilidad futura: analizar patrones históricos del usuario para:
- Ajustar thresholds del scorer según comportamiento pasado
- Detectar tipos de eventos donde el usuario suele atrasarse
- Sugerir tiempos de anticipación basados en eventos completados

En esta etapa (MVP), el módulo existe como placeholder arquitectural.
La lógica real se implementará en Fase 2 cuando haya suficientes datos.
"""


def analyze_user_patterns(user):
    """
    Analiza el historial de eventos del usuario para detectar patrones.
    Retorna un dict con métricas de comportamiento.

    Placeholder: retorna estructura vacía hasta Fase 2.
    """
    return {
        'avg_completion_rate': None,
        'typical_delay_days': None,
        'best_event_categories': [],
        'risk_categories': [],
    }


def get_personalized_thresholds(user):
    """
    Retorna thresholds ajustados al perfil del usuario.
    En MVP usa los defaults del engine.
    """
    return {
        'stalled_days': 7,
        'imminent_days': 3,
        'warning_days': 7,
        'upcoming_days': 30,
    }
