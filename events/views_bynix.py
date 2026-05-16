"""
views_bynix.py — Endpoints HTTP de Bynix (asistente IA de BIND).

Desacoplado de views.py para mantener el archivo principal manejable.
Contiene: event_assistant_chat, bynix_quick_capture, dashboard_assistant_chat
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from events.models import Event, BynixMessage
from modules.models import Task, Checklist, ChecklistItem

logger = logging.getLogger(__name__)


@login_required
def event_assistant_chat(request, pk):
    """
    Endpoint AJAX: recibe POST JSON con {query} y devuelve la respuesta de Bynix.
    Incluye campo 'action' cuando Bynix detecta intención de crear contenido.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    event = get_object_or_404(Event, pk=pk, owner=request.user)

    try:
        body = json.loads(request.body)
        query = body.get('query', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Formato inválido'}, status=400)

    if not query:
        return JsonResponse({'error': 'La consulta está vacía'}, status=400)

    from events.services.ai_service import build_event_context
    event_context = build_event_context(event)

    # Fusión con el Engine: inyectar health_score, momentum y alertas activas
    try:
        from events.engine.context import build_event_context as build_engine_ctx
        from events.engine.scorer import score_event
        from events.engine.decisions import derive_decisions
        _ectx = build_engine_ctx(event)
        _escore = score_event(_ectx)
        _decisions = derive_decisions(_ectx, _escore)
        event_context['engine_status'] = {
            'health_score': _escore.health_score,
            'health_label': _escore.health_label,
            'momentum': _escore.momentum_label,
            'alertas_activas': [d.message for d in _decisions[:3]],
        }
    except Exception:
        pass

    # Cargar historial desde BD (últimas 10 interacciones = 20 mensajes)
    history = list(
        BynixMessage.objects.filter(user=request.user, event=event)
        .order_by('-created_at')[:20]
        .values('role', 'content')
    )
    history = list(reversed(history))

    try:
        from events.services.ai_service import (
            get_event_assistant_response, deduct_credits,
            get_credits_reset_info, BYNIX_DAILY_CREDITS,
        )
        result    = get_event_assistant_response(query, event_context, history=history)
        remaining = deduct_credits(request.user.pk)
        usage_pct = round((1 - remaining / BYNIX_DAILY_CREDITS) * 100)

        # Persistir turno en BD
        BynixMessage.objects.create(user=request.user, event=event, role='user', content=query)
        BynixMessage.objects.create(user=request.user, event=event, role='assistant', content=result.get('response', ''))

        response_data = {
            'response':         result.get('response', ''),
            'action':           result.get('action'),
            'credits_remaining': remaining,
            'usage_percent':    usage_pct,
        }
        if remaining <= 0:
            reset_info = get_credits_reset_info(request.user.pk)
            response_data['reset_time'] = reset_info['reset_time']

        return JsonResponse(response_data)

    except Exception as exc:
        logger.warning("Bynix assistant error for event %s: %s", pk, exc)
        return JsonResponse({
            'response': 'Bynix está procesando. Intenta de nuevo en un momento.',
            'action':   None,
        })


@login_required
def bynix_quick_capture(request, pk):
    """
    Ejecuta un Quick Capture: genera y crea tareas + checklists en el evento actual
    a partir de una descripción en lenguaje natural enviada por Bynix.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    event = get_object_or_404(Event, pk=pk, owner=request.user)

    try:
        body = json.loads(request.body)
        description = body.get('description', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Formato inválido'}, status=400)

    if not description:
        return JsonResponse({'error': 'Descripción vacía'}, status=400)

    try:
        from events.services.ai_service import (
            quick_capture_event_structure, deduct_credits, BYNIX_DAILY_CREDITS,
        )
        structure = quick_capture_event_structure(description)

        created_tasks = []
        for task_data in structure.get('tareas', []):
            task = Task.objects.create(
                event=event,
                title=task_data.get('titulo', 'Tarea sin título')[:200],
                description=task_data.get('descripcion', ''),
                priority=task_data.get('prioridad', 'medium'),
                status='pending',
            )
            created_tasks.append(task.title)

        created_checklists = []
        for cl_data in structure.get('checklist', []):
            checklist = Checklist.objects.create(
                event=event,
                title=cl_data.get('titulo', 'Checklist')[:150],
            )
            for item_text in cl_data.get('items', []):
                ChecklistItem.objects.create(
                    checklist=checklist,
                    text=str(item_text)[:300],
                )
            created_checklists.append(checklist.title)

        remaining = deduct_credits(request.user.pk)
        usage_pct = round((1 - remaining / BYNIX_DAILY_CREDITS) * 100)

        return JsonResponse({
            'success':             True,
            'mensaje':             structure.get('mensaje', '¡Estructura creada con éxito!'),
            'tareas_creadas':      created_tasks,
            'checklists_creados':  created_checklists,
            'incluir_presupuesto': structure.get('incluir_presupuesto', False),
            'credits_remaining':   remaining,
            'usage_percent':       usage_pct,
        })

    except Exception as exc:
        logger.warning("Bynix quick capture error for event %s: %s", pk, exc)
        return JsonResponse(
            {'error': 'No pude generar la estructura. Intenta de nuevo.'},
            status=500,
        )


@login_required
def dashboard_assistant_chat(request):
    """
    Endpoint AJAX del Bynix global del Dashboard.
    No está vinculado a un evento específico — trabaja sobre el estado global del usuario.
    Soporta acciones: CREATE_EVENT, NAVIGATE_EVENT.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)
        query = body.get('query', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Formato inválido'}, status=400)

    if not query:
        return JsonResponse({'error': 'La consulta está vacía'}, status=400)

    try:
        from events.engine import run_engine_for_user
        from events.stats import compute_user_stats
        from events.services.ai_service import (
            build_dashboard_context, get_dashboard_assistant_response,
            deduct_credits, get_credits_reset_info, BYNIX_DAILY_CREDITS,
        )

        engine_output = run_engine_for_user(request.user)
        stats = compute_user_stats(request.user)
        dashboard_ctx = build_dashboard_context(request.user, engine_output, stats)

        # Cargar historial del dashboard desde BD (event=None, últimas 10 interacciones)
        history = list(
            BynixMessage.objects.filter(user=request.user, event=None)
            .order_by('-created_at')[:20]
            .values('role', 'content')
        )
        history = list(reversed(history))

        result = get_dashboard_assistant_response(query, dashboard_ctx, history=history)
        remaining = deduct_credits(request.user.pk)
        usage_pct = round((1 - remaining / BYNIX_DAILY_CREDITS) * 100)

        # Persistir turno en BD
        BynixMessage.objects.create(user=request.user, event=None, role='user', content=query)
        BynixMessage.objects.create(user=request.user, event=None, role='assistant', content=result.get('response', ''))

        response_data = {
            'response':          result.get('response', ''),
            'action':            result.get('action'),
            'credits_remaining': remaining,
            'usage_percent':     usage_pct,
        }
        if remaining <= 0:
            reset_info = get_credits_reset_info(request.user.pk)
            response_data['reset_time'] = reset_info['reset_time']

        return JsonResponse(response_data)

    except Exception as exc:
        logger.warning("Dashboard Bynix error: %s", exc)
        return JsonResponse({
            'response': 'Bynix está procesando. Intenta de nuevo en un momento.',
            'action': None,
        })
