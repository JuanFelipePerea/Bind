"""
Servicio centralizado para llamadas a Google Gemini.

Expone:
  - generate_structured_data(prompt, system_instruction, model_name)
      Función base: llama a Gemini y devuelve un dict JSON limpio.
  - generate_report_insights(stats)
      Genera análisis ejecutivo del reporte del usuario (resumen, riesgos,
      recomendaciones, tendencia y score de salud).
"""

import json
import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.5-flash-lite"

if not _API_KEY:
    logger.warning("GEMINI_API_KEY no definida — el servicio de IA estará inactivo.")

_client: genai.Client | None = genai.Client(api_key=_API_KEY) if _API_KEY else None


# ─── Sistema de créditos Bynix ───────────────────────────────────────────────

BYNIX_DAILY_CREDITS = 100
CREDIT_COST_PER_CALL = 10
_CREDITS_TTL = 86_400  # 24 horas


def _credits_key(user_id: int) -> str:
    return f"bynix_credits_{user_id}"


def _credits_set_at_key(user_id: int) -> str:
    return f"bynix_set_at_{user_id}"


def get_user_credits(user_id: int) -> int:
    """Retorna créditos disponibles. Inicializa a 100 si es el primer acceso del día."""
    from django.core.cache import cache
    credits = cache.get(_credits_key(user_id))
    if credits is None:
        credits = BYNIX_DAILY_CREDITS
        cache.set(_credits_key(user_id), credits, _CREDITS_TTL)
        cache.set(_credits_set_at_key(user_id), time.time(), _CREDITS_TTL)
    return credits


def deduct_credits(user_id: int) -> int:
    """
    Descuenta CREDIT_COST_PER_CALL créditos al usuario.
    Retorna créditos restantes (nunca negativo).
    """
    from django.core.cache import cache
    key = _credits_key(user_id)
    current = cache.get(key)
    if current is None:
        current = BYNIX_DAILY_CREDITS
    new_total = max(0, current - CREDIT_COST_PER_CALL)
    cache.set(key, new_total, _CREDITS_TTL)
    return new_total


def get_usage_percent(user_id: int) -> int:
    """Porcentaje de créditos USADOS (0 = sin uso, 100 = agotado)."""
    remaining = get_user_credits(user_id)
    return round((1 - remaining / BYNIX_DAILY_CREDITS) * 100)


def get_credits_reset_info(user_id: int) -> dict:
    """Retorna cuánto tiempo falta para que los créditos se reinicien."""
    from django.core.cache import cache
    set_at = cache.get(_credits_set_at_key(user_id))
    if set_at is None:
        return {"seconds_until": 0, "reset_time": "mañana"}
    elapsed = time.time() - set_at
    seconds_until = max(0, int(_CREDITS_TTL - elapsed))
    hours = seconds_until // 3600
    minutes = (seconds_until % 3600) // 60
    if seconds_until == 0:
        reset_time = "en breve"
    elif hours > 0:
        reset_time = f"en {hours}h {minutes}m"
    elif minutes > 0:
        reset_time = f"en {minutes} minutos"
    else:
        reset_time = "en menos de un minuto"
    return {"seconds_until": seconds_until, "reset_time": reset_time}


# ─── función base ────────────────────────────────────────────────────────────

def generate_structured_data(
    prompt: str,
    system_instruction: str = "",
    model_name: str = DEFAULT_MODEL,
) -> dict:
    """
    Llama a Gemini y devuelve un dict parseado desde JSON.

    Raises:
        ValueError   – si GEMINI_API_KEY no está configurada.
        RuntimeError – en errores de red, cuota o parseo.
    """
    if _client is None:
        raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno.")

    config_kwargs: dict = {
        "response_mime_type": "application/json",
        "temperature": 0.3,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    try:
        response = _client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        raw = (response.text or "").strip()

        # Protección extra por si el modelo envuelve en bloques markdown
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

        return json.loads(raw)

    except json.JSONDecodeError as exc:
        logger.error("Gemini devolvió respuesta no-JSON: %s", exc)
        raise RuntimeError(f"No se pudo parsear la respuesta de Gemini como JSON: {exc}") from exc
    except Exception as exc:
        logger.error("Error en llamada a Gemini API: %s", exc)
        raise RuntimeError(f"La llamada a Gemini falló: {exc}") from exc


# ─── función de dominio: insights del reporte ───────────────────────────────

_REPORT_SYSTEM = """
Eres un asistente de análisis de productividad para BIND, una plataforma de
gestión de eventos. Recibes métricas en español y respondes ÚNICAMENTE con JSON
válido (sin texto adicional, sin bloques markdown). El JSON debe seguir exactamente
el esquema indicado en el prompt.
""".strip()

_REPORT_SCHEMA = """
{
  "resumen": "<string: 2-3 oraciones ejecutivas sobre el estado general>",
  "tendencia": "<'positiva' | 'negativa' | 'estable'>",
  "score_salud": <entero 0-100>,
  "riesgos": [
    { "nivel": "<'alto' | 'medio' | 'bajo'>", "descripcion": "<string>" }
  ],
  "recomendaciones": ["<acción concreta 1>", "<acción concreta 2>", "..."]
}
""".strip()


def generate_report_insights(stats: dict) -> dict:
    """
    Genera un análisis ejecutivo basado en las estadísticas del usuario.

    Parámetros esperados (todos presentes en compute_user_stats):
        total_events, active_events, completed_events, cancelled_events,
        total_tasks, done_tasks, pending_tasks, inprog_tasks,
        task_completion_rate, high_tasks, overdue_tasks (queryset o list),
        total_attendees, confirmed_attendees, total_files.

    Devuelve el dict definido en _REPORT_SCHEMA.
    Raises RuntimeError si el servicio falla.
    """
    overdue_raw = stats.get("overdue_tasks", [])
    # Django QuerySet tiene .count(); list de Python no acepta count() sin args
    if hasattr(overdue_raw, "model"):
        overdue_count = overdue_raw.count()
    else:
        overdue_count = len(overdue_raw)

    prompt = f"""
Analiza las siguientes métricas de productividad y devuelve un JSON con este esquema:
{_REPORT_SCHEMA}

Métricas actuales:
- Eventos: {stats.get('total_events', 0)} total, {stats.get('active_events', 0)} activos,
  {stats.get('completed_events', 0)} completados, {stats.get('cancelled_events', 0)} cancelados.
- Tareas: {stats.get('total_tasks', 0)} total, {stats.get('done_tasks', 0)} completadas,
  {stats.get('inprog_tasks', 0)} en progreso, {stats.get('pending_tasks', 0)} pendientes.
- Tasa de completado de tareas: {stats.get('task_completion_rate', 0)}%.
- Tareas de alta prioridad: {stats.get('high_tasks', 0)}.
- Tareas vencidas: {overdue_count}.
- Asistentes: {stats.get('confirmed_attendees', 0)} confirmados de {stats.get('total_attendees', 0)}.
- Archivos registrados: {stats.get('total_files', 0)}.

Reglas para score_salud (0-100):
  • Base 60. +20 si tasa de completado ≥ 70%. -15 si hay tareas vencidas.
  • -10 si cancelled_events > completed_events. +10 si active_events > 0.

Devuelve máximo 3 riesgos y 4 recomendaciones, ordenados por impacto.
    """.strip()

    return generate_structured_data(prompt, system_instruction=_REPORT_SYSTEM)


# ─── Narrativa del dashboard · Bynix ────────────────────────────────────────

_BYNIX_SYSTEM = """
Eres Bynix, asistente experta de BIND. Tu tono es profesional, motivador y
extremadamente conciso. Responde ÚNICAMENTE con JSON válido (sin texto extra,
sin bloques markdown).
""".strip()


def generate_dashboard_narrative(stats: dict) -> dict:
    """
    Genera una narrativa motivadora del dashboard semanal.

    Recibe el dict de compute_user_stats().
    Devuelve {"narrative": "<2 oraciones máx>"}.
    Raises RuntimeError si el servicio falla.
    """
    overdue_raw = stats.get("overdue_tasks", [])
    overdue_count = overdue_raw.count() if hasattr(overdue_raw, "model") else len(overdue_raw)
    upcoming_count = len(stats.get("upcoming_events", []))

    prompt = f"""
Genera un resumen ejecutivo motivador de máximo 2 oraciones sobre el estado semanal
del usuario. Sé directo, orientado a la acción y en español. No uses emojis.

Métricas:
- Eventos activos: {stats.get('active_events', 0)}
- Tareas pendientes: {stats.get('pending_tasks', 0)}
- Tareas completadas: {stats.get('done_tasks', 0)}
- Tasa de completado: {stats.get('task_completion_rate', 0)}%
- Tareas vencidas: {overdue_count}
- Tareas de alta prioridad: {stats.get('high_tasks', 0)}
- Próximos eventos: {upcoming_count}

Responde con JSON: {{"narrative": "<máximo 2 oraciones motivadoras>"}}
    """.strip()

    return generate_structured_data(prompt, system_instruction=_BYNIX_SYSTEM)


# ─── Contexto enriquecido del evento para Bynix ─────────────────────────────

def build_event_context(event) -> dict:
    """Construye un contexto completo del evento para Bynix (presupuesto, asistentes, fechas)."""
    from django.utils import timezone
    from modules.models import Task, Attendee

    today = timezone.now().date()
    tasks = list(event.tasks.all())
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == 'done')
    overdue = [
        t for t in tasks
        if t.due_date and t.due_date < today
        and t.status != 'done'
    ]
    pending_high = [
        t for t in tasks
        if t.priority == 'high' and t.status != 'done'
    ]

    days_until = None
    if event.start_date:
        days_until = (event.start_date.date() - today).days

    attendees = event.attendees.all()
    attendees_list = list(attendees)
    confirmed = sum(1 for a in attendees_list if a.status == 'confirmed')
    pending_att = sum(1 for a in attendees_list if a.status == 'pending')

    budget_info = None
    try:
        b = event.budget
        budget_info = {
            'total': float(b.total_budget),
            'gastado': float(b.total_spent),
            'restante': float(b.remaining),
            'porcentaje_usado': b.usage_percentage,
            'moneda': b.currency,
        }
    except Exception:
        pass

    return {
        'nombre': event.name,
        'descripcion': event.description[:500] if event.description else '',
        'estado': event.get_status_display(),
        'dias_restantes': days_until,
        'ubicacion': event.location or 'No definida',
        'progreso_tareas': f"{done}/{total} ({int(done/total*100) if total else 0}%)",
        'tareas_vencidas': [t.title for t in overdue[:5]],
        'tareas_alta_prioridad_pendientes': [t.title for t in pending_high[:5]],
        'asistentes': {
            'total': len(attendees_list),
            'confirmados': confirmed,
            'pendientes': pending_att,
        },
        'presupuesto': budget_info,
    }


# ─── Agente operativo por evento · Bynix ────────────────────────────────────

_BYNIX_AGENT_SYSTEM = """
Eres Bynix, agente operativo de BIND — una plataforma de gestión de eventos.
Nunca dices "No puedo hacer eso." En su lugar, preparas estructuras y ejecutas acciones proactivamente.
Tu tono es profesional, motivador y directo. Máximo 3 oraciones en español.

Cuando el usuario quiere CREAR contenido (estructura de evento, tareas, checklist, módulo),
devuelve el campo "action" con la intención. Si no hay intención de crear, devuelve "action": null.

RESPONDE ÚNICAMENTE con JSON válido (sin texto extra, sin bloques markdown).

Sin acción de creación:
{"response": "<tu respuesta accionable>", "action": null}

Con acción de creación:
{
  "response": "<confirmación entusiasta de lo que vas a preparar>",
  "action": {
    "type": "CREATE_STRUCTURE",
    "label": "<qué crearás, ej: Estructura para evento de Mitos>",
    "description": "<descripción original del usuario>",
    "confirm_text": "<pregunta de confirmación, ofreciendo módulo de presupuesto si aplica>",
    "suggest_budget": true
  }
}
""".strip()


def get_event_assistant_response(query: str, event_context: dict, history: list = None) -> dict:
    """
    Genera una respuesta de Bynix a una consulta sobre un evento específico.
    Puede incluir una acción sugerida si detecta intención de crear contenido.

    event_context: resultado de build_event_context(event) con campos enriquecidos.
    history: lista de dicts {role: 'user'|'assistant', content: str} — últimas interacciones.
    Devuelve {"response": "...", "action": null | {...}}.
    Raises RuntimeError si el servicio falla.
    """
    overdue_text = "\n".join(
        f"  - {t}" for t in event_context.get("tareas_vencidas", [])
    ) or "  (ninguna)"

    high_text = "\n".join(
        f"  - {t}" for t in event_context.get("tareas_alta_prioridad_pendientes", [])
    ) or "  (ninguna)"

    asistentes = event_context.get("asistentes", {})
    presupuesto = event_context.get("presupuesto")
    budget_text = ""
    if presupuesto:
        pct = presupuesto.get("porcentaje_usado", 0)
        budget_text = (
            f"\n- Presupuesto: {presupuesto.get('gastado')} / "
            f"{presupuesto.get('total')} {presupuesto.get('moneda')} ({pct}% usado)"
        )

    history_block = ""
    if history:
        lines = [
            f"{'Usuario' if t['role'] == 'user' else 'Bynix'}: {t['content']}"
            for t in history
        ]
        history_block = "Historial reciente de la conversación:\n" + "\n".join(lines) + "\n\n"

    prompt = f"""
{history_block}Contexto del evento:
- Nombre: {event_context.get('nombre', 'Sin nombre')}
- Estado: {event_context.get('estado', '')} | Días restantes: {event_context.get('dias_restantes', 'N/A')}
- Ubicación: {event_context.get('ubicacion', 'No definida')}
- Progreso de tareas: {event_context.get('progreso_tareas', '0/0 (0%)')}
- Tareas vencidas:
{overdue_text}
- Tareas de alta prioridad pendientes:
{high_text}
- Asistentes: {asistentes.get('total', 0)} total, {asistentes.get('confirmados', 0)} confirmados, {asistentes.get('pendientes', 0)} pendientes{budget_text}

Consulta del usuario: {query}

Responde con JSON exacto según tu análisis:
Sin acción: {{"response": "<respuesta accionable en español, máx 3-4 oraciones>", "action": null}}
Con creación: {{"response": "<confirmación entusiasta>", "action": {{"type": "CREATE_STRUCTURE", "label": "<qué crearás>", "description": "<descripción del usuario>", "confirm_text": "<¿Deseas que cree...?>", "suggest_budget": true/false}}}}
    """.strip()

    result = generate_structured_data(prompt, system_instruction=_BYNIX_AGENT_SYSTEM)
    if "action" not in result:
        result["action"] = None
    if "response" not in result:
        result["response"] = ""
    return result


# ─── Quick Capture: genera estructura de tareas + checklist ─────────────────

_QUICK_CAPTURE_SYSTEM = """
Eres Bynix, agente creativo de BIND. Generas estructuras completas de tareas y checklists
para eventos. Responde ÚNICAMENTE con JSON válido (sin texto extra, sin bloques markdown).
""".strip()


def quick_capture_event_structure(description: str) -> dict:
    """
    Genera tareas y checklists para el evento actual a partir de una descripción.

    Devuelve {
        tareas: [{titulo, prioridad, descripcion}],
        checklist: [{titulo, items: [...]}],
        incluir_presupuesto: bool,
        mensaje: str
    }
    Raises RuntimeError si el servicio falla.
    """
    prompt = f"""
Basándote en esta descripción, genera tareas y checklists relevantes para organizar el evento.

Descripción: {description}

Genera exactamente este JSON:
{{
  "tareas": [
    {{"titulo": "...", "prioridad": "high|medium|low", "descripcion": "..."}}
  ],
  "checklist": [
    {{"titulo": "...", "items": ["...", "..."]}}
  ],
  "incluir_presupuesto": true,
  "mensaje": "<mensaje de Bynix confirmando lo que preparó, máx 2 oraciones, entusiasta y proactivo>"
}}

Reglas:
- Entre 3 y 6 tareas concretas y accionables
- Entre 1 y 2 checklists con 3 a 6 ítems cada uno
- incluir_presupuesto: true si el evento involucra gastos (conciertos, conferencias, bodas, etc.)
- El mensaje menciona lo que se creó y ofrece agregar presupuesto si aplica
    """.strip()

    return generate_structured_data(prompt, system_instruction=_QUICK_CAPTURE_SYSTEM)
