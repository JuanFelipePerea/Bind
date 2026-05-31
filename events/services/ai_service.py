"""
Servicio centralizado para llamadas a Groq Cloud (compatible con la API de OpenAI).

Expone:
  - generate_structured_data(prompt, system_instruction, model_name)
      Función base: llama a Groq y devuelve un dict JSON limpio.
  - generate_report_insights(stats)
      Genera análisis ejecutivo del reporte del usuario (resumen, riesgos,
      recomendaciones, tendencia y score de salud).
"""

import json
import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_MODEL = "llama-3.3-70b-versatile"

if not _API_KEY:
    logger.warning("GROQ_API_KEY no definida — el servicio de IA estará inactivo.")

_client: OpenAI | None = (
    OpenAI(api_key=_API_KEY, base_url="https://api.groq.com/openai/v1") if _API_KEY else None
)


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
    Llama a Grok (xAI) y devuelve un dict parseado desde JSON.

    Construye la lista de mensajes en el formato estándar de OpenAI:
      [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

    Raises:
        ValueError   – si GROK_API_KEY no está configurada.
        RuntimeError – en errores de red, cuota o parseo.
    """
    if _client is None:
        raise ValueError("GROQ_API_KEY no está configurada en las variables de entorno.")

    messages: list[dict] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    try:
        response = _client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()

        # Protección extra por si el modelo envuelve en bloques markdown
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

        return json.loads(raw)

    except json.JSONDecodeError as exc:
        logger.error("Groq devolvió respuesta no-JSON: %s", exc)
        raise RuntimeError(f"No se pudo parsear la respuesta de Groq como JSON: {exc}") from exc
    except Exception as exc:
        logger.error("Error en llamada a Groq API: %s", exc)
        raise RuntimeError(f"La llamada a Groq falló: {exc}") from exc


# ─── función de dominio: insights del reporte ───────────────────────────────

_REPORT_SYSTEM = """
Eres Bynix, asistente de análisis de BIND. Recibes métricas reales de un usuario
y generas un informe ejecutivo honesto, concreto y accionable — no genérico.

TONO: Profesional con calidez. Directo. Sin frases vacías como "¡Excelente trabajo!".
Si los datos muestran problemas, dilo con claridad y ofrece soluciones específicas.
Si todo va bien, reconócelo con sobriedad.

Responde ÚNICAMENTE con JSON válido (sin texto extra, sin bloques markdown).
El JSON debe seguir exactamente el esquema indicado en el prompt.
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
Eres Bynix, asistente de BIND. Generas un resumen semanal breve para el dashboard
del usuario. Tu voz es profesional pero cercana: como un colega competente que
va directo al grano y sabe motivar sin exagerar.

Sé honesta: si hay problemas, nómbralos. Si hay logros, reconócelos con sobriedad.
Máximo 2 oraciones. Orientadas a la acción. En español.

Responde ÚNICAMENTE con JSON válido: {"narrative": "<texto>"}
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

    # Momentos — hitos temporales del evento
    momentos_info = []
    try:
        for m in event.momentos.order_by('hora_inicio'):
            entry = {
                'titulo':      m.titulo,
                'tipo':        m.get_tipo_display(),
                'importancia': m.get_importancia_display(),
                'hora_inicio': m.hora_inicio.strftime('%d/%m/%Y %H:%M'),
            }
            if m.hora_fin:
                entry['hora_fin'] = m.hora_fin.strftime('%d/%m/%Y %H:%M')
            if m.descripcion:
                entry['descripcion'] = m.descripcion[:200]
            momentos_info.append(entry)
    except Exception:
        pass

    # Checklists — progreso y ítems pendientes
    checklists_info = []
    try:
        for cl in event.checklists.prefetch_related('items').all():
            items = list(cl.items.all())
            total_items = len(items)
            done_items = sum(1 for i in items if i.is_checked)
            pct = int(done_items / total_items * 100) if total_items else 0
            checklists_info.append({
                'titulo': cl.title,
                'progreso': f"{done_items}/{total_items} ({pct}%)",
                'items_pendientes': [i.text for i in items if not i.is_checked][:5],
            })
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
        'momentos': momentos_info,
        'checklists': checklists_info,
        # engine_status se inyecta desde la view (no aquí) para mantener separación de capas
    }


# ─── Agente operativo por evento · Bynix ────────────────────────────────────

SYSTEM_PROMPT = """
Eres Bynix, la asistente operativa de {user_name} en BIND — una plataforma de
gestión de eventos. Tienes acceso al estado completo del evento y puedes ejecutar
acciones reales en su nombre.

VOZ Y TONO:
- Profesional con calidez. Como una asistente personal competente que conoce bien
  al usuario y habla con confianza, no como un bot corporativo.
- Usa el nombre del usuario de forma natural (no en cada frase, solo cuando encaje).
- En español. Sin emojis excesivos — solo cuando aporten claridad visual.
- Respuestas ricas cuando el contexto lo merece. No te cortes artificialmente.
  Si el usuario pide un análisis, analiza. Si pide un plan, planea en detalle.
- Nunca respondas con frases vacías como "¡Claro!", "¡Por supuesto!" o
  "¡Excelente pregunta!". Ve directo al valor.

EJEMPLOS DE BUEN TONO:
  ✓ "Hola {user_name}. El evento va bien en general, pero hay una señal de alerta:
     tienes 3 tareas vencidas y solo 5 días para el inicio. Te recomiendo resolverlas
     hoy. ¿Quieres que las priorice por urgencia?"
  ✓ "El presupuesto ya está al 84% — queda poco margen. Antes de aprobar nuevos
     gastos, vale la pena revisar qué está pendiente de pago."
  ✗ "¡Claro! Puedo ayudarte con eso. El evento tiene varias tareas..."

MOTOR DE ANÁLISIS (prioridad alta):
El contexto incluye "engine_status" con el análisis del motor de BIND. Úsalo siempre:
- health_score < 40: evento crítico — mencionarlo aunque no te lo pidan.
- health_score < 60: advertir sobre riesgo con datos concretos.
- momentum "stalled" o "slowing": sugerir retomar actividad con acciones específicas.
- "alertas_activas": cítalas textualmente, no las parafrasees.

CAPACIDADES QUE PUEDES EJECUTAR:
1. Crear tareas — responde con action: {{"type": "CREATE_STRUCTURE", "label": "tareas", ...}}
2. Crear checklist — mismo mecanismo con label "checklist".
3. Análisis puro — responde solo con "response", action null.

LÍMITES DUROS — NUNCA violarlos:
- NUNCA afirmes haber eliminado, modificado, cerrado, archivado o marcado como hecho
  ningún evento, tarea, asistente ni otro registro. No puedes ejecutar esas acciones.
- Si el usuario pide eliminar o cerrar algo, responde: "No puedo hacer eso directamente.
  Ve a [ruta relevante] y hazlo tú." Luego da el link o las instrucciones exactas.
- NUNCA inventes datos que no estén en el contexto.
- NUNCA confirmes como hecho algo que no generaste con una action JSON.

REGLAS DE CONTENIDO:
- "¿Cómo voy?" → empieza con health_score y momentum, luego tareas, checklists,
  presupuesto. Termina con una sugerencia concreta.
- Tareas vencidas → mencionarlas siempre que existan, aunque no pregunten.
- Presupuesto > 80% → advertir con el porcentaje exacto.
- Faltan ≤ 7 días + tareas high pendientes → urgencia explícita.
- Checklists con < 50% completitud y evento próximo → mencionarlo.
- Solo usa datos del contexto. Si falta información, pregunta.

RESPONDE ÚNICAMENTE con JSON válido (sin texto extra, sin bloques markdown).
Sin acción: {{"response": "<respuesta>", "action": null}}
Con acción: {{"response": "<confirmación breve>", "action": {{"type": "CREATE_STRUCTURE", "label": "<qué crearás>", "description": "<desc>", "confirm_text": "<pregunta al usuario>", "suggest_budget": true/false}}}}

CONTEXTO DEL EVENTO:
{event_context}

HISTORIAL RECIENTE:
{history_block}
""".strip()


def get_event_assistant_response(
    query: str,
    event_context: dict,
    history: list = None,
    user_name: str = "usuario",
) -> dict:
    """
    Genera una respuesta de Bynix a una consulta sobre un evento específico.
    Puede incluir una acción sugerida si detecta intención de crear contenido.

    event_context: resultado de build_event_context(event) con campos enriquecidos.
    history: lista de dicts {role: 'user'|'assistant', content: str} — últimas interacciones.
    user_name: nombre del usuario autenticado para personalizar las respuestas.
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

    formatted_system = SYSTEM_PROMPT.format(
        user_name=user_name,
        event_context=json.dumps(event_context, ensure_ascii=False, indent=2),
        history_block=history_block or "(ninguno)",
    )
    result = generate_structured_data(prompt, system_instruction=formatted_system)
    if "action" not in result:
        result["action"] = None
    if "response" not in result:
        result["response"] = ""
    return result


# ─── Quick Capture: genera estructura de tareas + checklist ─────────────────

_QUICK_CAPTURE_SYSTEM = """
Eres Bynix, asistente de BIND. A partir de una descripción libre del usuario, generas
una estructura de trabajo completa y práctica: tareas concretas y checklists útiles.

TONO del campo "mensaje": cercano, directo, sin exagerar. Confirma qué creaste y
ofrece el siguiente paso natural. Ejemplo:
  ✓ "Creé 5 tareas y un checklist de logística. Si el evento tiene gastos,
     puedo añadir también una estructura de presupuesto."
  ✗ "¡Listo! He preparado una estructura increíble para tu evento."

Responde ÚNICAMENTE con JSON válido (sin texto extra, sin bloques markdown).
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


# ─── Dashboard Bynix — contexto global del usuario ──────────────────────────

_DASHBOARD_BYNIX_SYSTEM = """
Eres Bynix, la asistente estratégica de BIND. En el dashboard tienes visibilidad
completa sobre todos los eventos del usuario y actúas como su mano derecha operativa.

VOZ Y TONO:
- Profesional con calidez. Directa. Como una asistente personal que conoce bien
  al usuario y le habla con confianza, no como un sistema automatizado.
- Usa el nombre del usuario (está en el contexto como "usuario") de forma natural.
- En español. Sin emojis excesivos.
- Respuestas suficientemente ricas: si hay mucho que decir, dilo. No te cortes.
- Nunca uses frases de relleno. Ve directo al punto que importa.

EJEMPLOS DE BUEN TONO:
  ✓ "Hola [nombre]. Tienes 2 eventos que necesitan atención hoy: 'Lanzamiento Q3'
     (salud 35/100, 3 tareas vencidas) y 'Conferencia Anual' (presupuesto al 91%).
     ¿Por cuál empezamos?"
  ✓ "Todo en orden por ahora. Tu tasa de completado esta semana es del 78% —
     buen ritmo. El próximo hito es 'Conferencia Anual' en 12 días."
  ✗ "¡Hola! Soy Bynix y estoy aquí para ayudarte con tus eventos."

CAPACIDADES EN EL DASHBOARD:
1. Orientar → qué evento necesita atención inmediata, con datos concretos.
2. Crear evento → extrae nombre, descripción y fecha del mensaje del usuario:
   {{"type": "CREATE_EVENT", "name": "...", "description": "...", "start_date": "YYYY-MM-DD o null"}}
3. Navegar a evento → cuando el usuario quiera ir a uno específico:
   {{"type": "NAVIGATE_EVENT", "event_id": <id>, "event_name": "..."}}
4. Análisis global → responde con datos reales del contexto, sin inventar.

LÍMITES DUROS — NUNCA violarlos:
- NUNCA afirmes haber eliminado, cerrado, archivado o modificado ningún evento,
  tarea ni registro. Esas operaciones NO están disponibles para ti.
- Si el usuario pide eliminar o cerrar eventos: explica cómo hacerlo manualmente
  (ir a la lista de proyectos, abrir cada uno y usar el botón Eliminar).
  Nunca digas "ya lo hice" ni "listo".
- NUNCA inventes información que no esté en el contexto recibido.
- NUNCA confirmes como ejecutada una acción que no generaste como action JSON.

REGLAS DE CONTENIDO:
- Eventos con health_score < 40 → mencionarlos SIEMPRE, aunque no pregunten.
- needs_attention = true + saludo del usuario → responde con el evento más urgente
  y datos concretos (nombre, score, problema principal).
- Si todo va bien, dilo con datos: tasa de completado, próximo evento, etc.
- Solo usa datos del contexto. Si falta algo, pregunta.

RESPONDE ÚNICAMENTE con JSON válido (sin texto extra, sin bloques markdown).
Sin acción: {{"response": "<respuesta>", "action": null}}
Con acción: {{"response": "<confirmación breve>", "action": {{...}}}}

CONTEXTO GLOBAL DEL USUARIO:
{dashboard_context}

HISTORIAL RECIENTE:
{history_block}
""".strip()


def build_dashboard_context(user, engine_output: dict, stats: dict) -> dict:
    """
    Construye el contexto global del usuario para el Dashboard Bynix.
    Combina engine_output (scores + decisions) con stats agregados.
    """
    from events.models import Event

    event_scores = engine_output.get('event_scores', {})
    event_contexts = engine_output.get('event_contexts', {})
    all_decisions = engine_output.get('all_decisions', [])
    summary = engine_output.get('dashboard_summary', {})

    eventos_info = []
    events_qs = Event.objects.filter(
        owner=user, status__in=['active', 'draft']
    ).only('id', 'name', 'start_date', 'status').order_by('-updated_at')[:10]

    for event in events_qs:
        score = event_scores.get(event.pk)
        ctx = event_contexts.get(event.pk)
        entry = {
            'id': event.pk,
            'nombre': event.name,
            'estado': event.get_status_display(),
        }
        if event.start_date:
            entry['fecha'] = event.start_date.strftime('%d/%m/%Y')
        if score:
            entry['health_score'] = score.health_score
            entry['health_label'] = score.health_label
            entry['momentum'] = score.momentum_label
        if ctx:
            entry['progreso_tareas'] = f"{ctx.task_done}/{ctx.task_total}"
            entry['tareas_vencidas'] = ctx.task_overdue
            if ctx.days_until is not None:
                entry['dias_restantes'] = ctx.days_until
        eventos_info.append(entry)

    return {
        'usuario': user.get_full_name() or user.username,
        'resumen': {
            'eventos_activos': stats.get('active_events', 0),
            'eventos_criticos': summary.get('events_at_risk', 0),
            'tareas_pendientes': stats.get('pending_tasks', 0),
            'tareas_vencidas': len(stats.get('overdue_tasks', [])) if isinstance(stats.get('overdue_tasks'), list) else 0,
            'tasa_completado': stats.get('task_completion_rate', 0),
        },
        'necesita_atencion': summary.get('needs_attention', False),
        'alertas_criticas': summary.get('critical_count', 0),
        'eventos': eventos_info,
        'decision_top': all_decisions[0].message if all_decisions else None,
    }


def get_dashboard_assistant_response(query: str, dashboard_context: dict, history: list = None) -> dict:
    """
    Genera una respuesta de Bynix en el contexto global del dashboard.
    Soporta acciones CREATE_EVENT y NAVIGATE_EVENT.
    Devuelve {"response": "...", "action": null | {...}}.
    """
    history_block = ""
    if history:
        lines = [
            f"{'Usuario' if t['role'] == 'user' else 'Bynix'}: {t['content']}"
            for t in history
        ]
        history_block = "Historial reciente:\n" + "\n".join(lines) + "\n\n"

    eventos_resumen = ""
    for ev in dashboard_context.get('eventos', []):
        score_str = f" | Salud: {ev.get('health_score', '?')}/100" if 'health_score' in ev else ""
        dias_str = f" | {ev.get('dias_restantes')} días" if 'dias_restantes' in ev else ""
        vencidas_str = f" | {ev.get('tareas_vencidas')} vencidas" if ev.get('tareas_vencidas') else ""
        eventos_resumen += f"  - [{ev['id']}] {ev['nombre']}{score_str}{dias_str}{vencidas_str}\n"

    prompt = f"""
{history_block}Contexto global:
- Eventos activos: {dashboard_context['resumen']['eventos_activos']}
- Eventos en riesgo/críticos: {dashboard_context['resumen']['eventos_criticos']}
- Tareas pendientes: {dashboard_context['resumen']['tareas_pendientes']}
- Tareas vencidas: {dashboard_context['resumen']['tareas_vencidas']}
- Tasa de completado: {dashboard_context['resumen']['tasa_completado']}%
- Necesita atención: {dashboard_context['necesita_atencion']}
- Alerta principal: {dashboard_context.get('decision_top') or 'ninguna'}

Eventos del usuario:
{eventos_resumen or '  (ninguno activo)'}

Consulta del usuario: {query}

Responde con JSON exacto:
Sin acción: {{"response": "<respuesta directa en español>", "action": null}}
Crear evento: {{"response": "<confirmación>", "action": {{"type": "CREATE_EVENT", "name": "<nombre>", "description": "<desc o vacío>", "start_date": "<YYYY-MM-DD o null>"}}}}
Navegar evento: {{"response": "<confirmación>", "action": {{"type": "NAVIGATE_EVENT", "event_id": <id>, "event_name": "<nombre>"}}}}
    """.strip()

    formatted_system = _DASHBOARD_BYNIX_SYSTEM.format(
        dashboard_context=json.dumps(dashboard_context, ensure_ascii=False, indent=2),
        history_block=history_block or "(ninguno)",
    )
    result = generate_structured_data(prompt, system_instruction=formatted_system)
    if "action" not in result:
        result["action"] = None
    if "response" not in result:
        result["response"] = ""
    return result
