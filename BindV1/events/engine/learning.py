"""
Learning — módulo de aprendizaje y mejora continua del engine.

Analiza los EngineMetrics acumulados del usuario para detectar:
- Tipos de decisión que el usuario nunca sigue (bajar threshold implícito)
- Tipos donde siempre actúa rápido (mantener o subir threshold)
- Tasa general de acción vs descarte

Los thresholds personalizados son consumidos por el scorer y el alert_engine
para generar decisiones más relevantes por usuario.
"""


def analyze_user_patterns(user):
    """
    Analiza el historial de EngineMetrics del usuario y retorna un dict
    con métricas de comportamiento por tipo de decisión.

    Retorna:
    {
        'avg_action_rate': float | None,  # 0.0–1.0 tasa global de acción
        'by_type': {
            '<decision_type>': {
                'action_rate': float,  # fracción de veces que el usuario actuó
                'total': int,
                'acted': int,
            }
        },
        'low_follow_types': [str],   # tipos con action_rate < 0.2
        'high_follow_types': [str],  # tipos con action_rate > 0.8
    }
    """
    from events.models import EngineMetrics

    metrics = EngineMetrics.objects.filter(user=user, user_acted__isnull=False)
    total_count = metrics.count()

    if total_count == 0:
        return {
            'avg_action_rate': None,
            'by_type': {},
            'low_follow_types': [],
            'high_follow_types': [],
        }

    # Agrupar por tipo de decisión en Python (evitar múltiples queries)
    by_type = {}
    total_acted = 0
    for m in metrics.values('decision_type', 'user_acted'):
        dt = m['decision_type']
        acted = bool(m['user_acted'])
        if dt not in by_type:
            by_type[dt] = {'total': 0, 'acted': 0}
        by_type[dt]['total'] += 1
        if acted:
            by_type[dt]['acted'] += 1
            total_acted += 1

    # Calcular action_rate por tipo
    for dt, stats in by_type.items():
        stats['action_rate'] = stats['acted'] / stats['total'] if stats['total'] > 0 else 0.0

    avg_action_rate = total_acted / total_count

    low_follow = [dt for dt, s in by_type.items() if s['action_rate'] < 0.2]
    high_follow = [dt for dt, s in by_type.items() if s['action_rate'] > 0.8]

    return {
        'avg_action_rate': avg_action_rate,
        'by_type': by_type,
        'low_follow_types': low_follow,
        'high_follow_types': high_follow,
    }


def get_personalized_thresholds(user):
    """
    Retorna thresholds ajustados al perfil del usuario basándose en
    los patrones detectados por analyze_user_patterns().

    Si el usuario ignora constantemente las alertas de tipo 'stalled',
    el threshold de días inactivos se eleva para reducir ruido.
    Si siempre actúa ante alertas de deadline, se mantiene el threshold agresivo.
    """
    defaults = {
        'stalled_days': 7,
        'imminent_days': 3,
        'warning_days': 7,
        'upcoming_days': 30,
    }

    patterns = analyze_user_patterns(user)
    if patterns['avg_action_rate'] is None:
        return defaults

    by_type = patterns['by_type']

    # Si el usuario ignora alertas de 'stalled', darle más días de margen
    stalled_stats = by_type.get('stalled', {})
    if stalled_stats.get('action_rate', 1.0) < 0.2 and stalled_stats.get('total', 0) >= 3:
        defaults['stalled_days'] = 14  # ampliar de 7 a 14

    # Si el usuario actúa ante deadlines con alta consistencia, mantener agresivo
    deadline_stats = by_type.get('deadline', {})
    if deadline_stats.get('action_rate', 0.0) > 0.8 and deadline_stats.get('total', 0) >= 3:
        defaults['imminent_days'] = 3   # mantener threshold estricto
        defaults['warning_days'] = 7

    # Si el usuario ignora asistentes, relajar threshold
    attendance_stats = by_type.get('attendance', {})
    if attendance_stats.get('action_rate', 1.0) < 0.2 and attendance_stats.get('total', 0) >= 3:
        defaults['warning_days'] = 3  # solo alertar cuando sea muy inminente

    return defaults
