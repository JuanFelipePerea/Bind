"""
views_collaborator.py — Endpoints de colaboración en eventos de BIND.
Desacoplado de views.py siguiendo la directriz arquitectónica de Round 3.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from events.models import Event, EventCollaborator

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(['GET'])
def list_collaborators(request, pk):
    """Retorna los colaboradores activos de un evento (owner o colaborador puede consultar)."""
    event = get_object_or_404(Event, pk=pk)

    # Solo el owner o un colaborador existente puede ver la lista
    is_owner = event.owner == request.user
    is_collab = EventCollaborator.objects.filter(event=event, user=request.user, accepted=True).exists()
    if not (is_owner or is_collab):
        return JsonResponse({'error': 'Sin acceso'}, status=403)

    collabs = EventCollaborator.objects.filter(event=event).select_related('user', 'invited_by')
    data = [
        {
            'id':          c.pk,
            'username':    c.user.username,
            'email':       c.user.email,
            'full_name':   c.user.get_full_name(),
            'role':        c.role,
            'accepted':    c.accepted,
            'invited_by':  c.invited_by.username,
            'invited_at':  c.invited_at.isoformat(),
        }
        for c in collabs
    ]
    return JsonResponse({'collaborators': data})


@login_required
@require_http_methods(['POST'])
def invite_collaborator(request, pk):
    """
    Invita a un usuario existente a colaborar en el evento.
    Body JSON: {email: str, role: 'editor'|'viewer'}
    Solo el owner puede invitar.
    """
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    try:
        body = json.loads(request.body)
        email = body.get('email', '').strip().lower()
        role  = body.get('role', 'viewer')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Formato inválido'}, status=400)

    if not email:
        return JsonResponse({'error': 'Email requerido'}, status=400)
    if role not in ('editor', 'viewer'):
        return JsonResponse({'error': 'Rol inválido'}, status=400)
    if email == request.user.email:
        return JsonResponse({'error': 'No puedes invitarte a ti mismo'}, status=400)

    try:
        target_user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'No existe un usuario con ese email'}, status=404)

    collab, created = EventCollaborator.objects.get_or_create(
        event=event,
        user=target_user,
        defaults={'invited_by': request.user, 'role': role},
    )
    if not created:
        # Ya invitado — actualizar rol si cambió
        if collab.role != role:
            collab.role = role
            collab.save(update_fields=['role'])
        return JsonResponse({
            'status':  'already_invited',
            'accepted': collab.accepted,
            'role':    collab.role,
        })

    return JsonResponse({
        'status':   'invited',
        'username': target_user.username,
        'role':     role,
    }, status=201)


@login_required
@require_http_methods(['POST'])
def accept_invitation(request, pk):
    """
    El usuario autenticado acepta su invitación al evento pk.
    - AJAX (X-Requested-With: XMLHttpRequest) → JsonResponse
    - Form POST normal → redirect con mensaje flash
    """
    from django.contrib import messages as _msgs
    event   = get_object_or_404(Event, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        collab = EventCollaborator.objects.get(event=event, user=request.user)
    except EventCollaborator.DoesNotExist:
        if is_ajax:
            return JsonResponse({'error': 'No tienes una invitación para este evento'}, status=404)
        _msgs.error(request, 'No tienes una invitación para ese evento.')
        return redirect('events:dashboard')

    if collab.accepted:
        if is_ajax:
            return JsonResponse({'status': 'already_accepted', 'role': collab.role})
        _msgs.info(request, f'Ya eres colaborador en "{event.name}".')
        return redirect('events:event_detail', pk=pk)

    collab.accepted = True
    collab.save(update_fields=['accepted'])

    if is_ajax:
        return JsonResponse({'status': 'accepted', 'event': event.name, 'role': collab.role})

    _msgs.success(request, f'¡Ahora colaboras en "{event.name}" como {collab.role}!')
    return redirect('events:event_detail', pk=pk)


@login_required
@require_http_methods(['POST'])
def decline_invitation(request, pk):
    """El usuario autenticado rechaza su invitación al evento pk (elimina el registro)."""
    from django.contrib import messages as _msgs
    event   = get_object_or_404(Event, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        collab = EventCollaborator.objects.get(event=event, user=request.user, accepted=False)
    except EventCollaborator.DoesNotExist:
        if is_ajax:
            return JsonResponse({'error': 'Sin invitación pendiente para este evento'}, status=404)
        return redirect('events:dashboard')
    collab.delete()
    if is_ajax:
        return JsonResponse({'status': 'declined', 'event': event.name})
    _msgs.info(request, f'Invitación a "{event.name}" rechazada.')
    return redirect('events:dashboard')


@login_required
@require_http_methods(['POST'])
def remove_collaborator(request, pk, collab_pk):
    """Elimina un colaborador del evento. Solo el owner puede hacerlo."""
    event  = get_object_or_404(Event, pk=pk, owner=request.user)
    collab = get_object_or_404(EventCollaborator, pk=collab_pk, event=event)
    collab.delete()
    return JsonResponse({'status': 'removed'})
