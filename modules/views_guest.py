"""
views_guest.py — Portal público de invitados y envío masivo de invitaciones.
Desacoplado de views.py (directriz arquitectónica BIND).
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from events.models import Event
from modules.models import Attendee, AttendeePreference

logger = logging.getLogger(__name__)

MAX_BULK_SEND = 50


@login_required
@require_http_methods(['POST'])
def send_invitations(request, event_pk):
    event      = get_object_or_404(Event, pk=event_pk, owner=request.user)
    candidates = (
        Attendee.objects.filter(event=event)
        .exclude(email='')
        .exclude(status='declined')
    )

    total   = candidates.count()
    to_send = candidates[:MAX_BULK_SEND]
    sent    = 0
    errors  = 0

    # Preparar adjunto usando el storage backend (soporta Cloudinary con auth)
    attachment = None
    if event.invitation_file:
        try:
            storage = event.invitation_file.storage
            filename = event.invitation_file.name.split('/')[-1] or 'invitacion.pdf'
            with storage.open(event.invitation_file.name, 'rb') as f:
                file_bytes = f.read()
            attachment = (filename, file_bytes, 'application/octet-stream')
        except Exception as exc:
            logger.warning("No se pudo leer invitation_file evento %s: %s", event_pk, exc)

    now = timezone.now()
    for attendee in to_send:
        try:
            path = reverse('guest_respond', args=[str(attendee.invitation_token)])
            magic_link = (
                settings.SITE_URL + path
                if getattr(settings, 'SITE_URL', '')
                else request.build_absolute_uri(path)
            )

            body_lines = [
                f"Hola {attendee.name},",
                "",
                f"Has sido invitado/a a: {event.name}",
            ]
            if event.start_date:
                body_lines.append(f"Fecha: {event.start_date.strftime('%d %b %Y, %H:%M')}")
            if event.location:
                body_lines.append(f"Lugar: {event.location}")
            body_lines += [
                "",
                "Por favor confirma tu asistencia haciendo clic aquí:",
                magic_link,
                "",
                "— Equipo BIND",
            ]

            msg = EmailMessage(
                subject=f"Invitación: {event.name}",
                body='\n'.join(body_lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[attendee.email],
            )
            if attachment:
                msg.attach(*attachment)
            msg.send()

            # Solo actualizar timestamps si el envío fue exitoso
            attendee.invitation_sent_at = now
            attendee.token_expires_at   = now + timedelta(days=30)
            attendee.save(update_fields=['invitation_sent_at', 'token_expires_at'])
            sent += 1

        except Exception as exc:
            logger.error(
                "Error enviando invitación a %s (tipo: %s): %s",
                attendee.email, type(exc).__name__, exc,
            )
            errors += 1

    summary = f"{sent} invitación(es) enviada(s)."
    if errors:
        summary += f" {errors} con error."
    if total > MAX_BULK_SEND:
        summary += f" (Primeras {MAX_BULK_SEND} de {total} — repite para continuar.)"

    messages.success(request, summary)
    return redirect('modules:attendee_list', event_pk=event_pk)


def guest_respond(request, token):
    try:
        attendee = Attendee.objects.select_related('event', 'event__owner').get(
            invitation_token=token
        )
    except Attendee.DoesNotExist:
        return render(request, 'modules/guest_respond.html', {
            'error': 'Invitación no encontrada o inválida.',
        })

    if attendee.token_expires_at and timezone.now() > attendee.token_expires_at:
        return render(request, 'modules/guest_respond.html', {
            'error': 'Este enlace ha expirado. Contacta al organizador para recibir uno nuevo.',
            'event': attendee.event,
        })

    try:
        existing_pref = attendee.preference
    except AttendeePreference.DoesNotExist:
        existing_pref = None

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        if new_status not in ('confirmed', 'declined'):
            return render(request, 'modules/guest_respond.html', {
                'attendee':     attendee,
                'event':        attendee.event,
                'existing_pref': existing_pref,
                'error_form':   'Selecciona una opción válida.',
            })

        attendee.status = new_status
        attendee.save(update_fields=['status'])

        if new_status == 'confirmed':
            dietary       = request.POST.get('dietary', 'none')
            accessibility = request.POST.get('accessibility') == 'on'
            notes         = request.POST.get('notes', '').strip()
            AttendeePreference.objects.update_or_create(
                attendee=attendee,
                defaults={
                    'dietary':       dietary,
                    'accessibility': accessibility,
                    'notes':         notes,
                },
            )

        return render(request, 'modules/guest_respond.html', {
            'attendee':  attendee,
            'event':     attendee.event,
            'confirmed': new_status == 'confirmed',
            'declined':  new_status == 'declined',
            'done':      True,
        })

    return render(request, 'modules/guest_respond.html', {
        'attendee':      attendee,
        'event':         attendee.event,
        'existing_pref': existing_pref,
    })
