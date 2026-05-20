from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
import random
import re
from datetime import timedelta

_2FA_CODE_EXPIRY_MINUTES = 5

from .models import UserProfile

def index_view(request):
    """Landing page pública de BIND."""
    # Si ya está autenticado, redirigir directo al dashboard
    if request.user.is_authenticated:
        return redirect('events:dashboard')
    return render(request, 'accounts/index.html')

# ─── Helper: verificar si el usuario tiene privilegios de admin ───────────────

def is_bind_admin(user):
    """
    Retorna True si el usuario es superuser de Django
    O si tiene el rol 'admin' en su UserProfile de BIND.
    """
    if user.is_superuser:
        return True
    try:
        return user.profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False


# ─── Autenticación ────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('events:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user:
            profile, _ = UserProfile.objects.get_or_create(user=user)

            # Si tiene 2FA activado, guardar en sesión y pedir código
            if profile.two_factor_enabled:
                request.session['2fa_pending_user_id'] = user.id
                code = _generate_2fa_code()
                profile.two_factor_secret = code
                profile.two_factor_sent_at = timezone.now()
                profile.save()
                send_mail(
                    subject='Tu código de verificación BIND',
                    message=f'Hola {user.first_name or user.username},\n\nTu código de verificación es: {code}\n\nVálido por 5 minutos.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                messages.info(request, 'Ingresa el código enviado a tu email.')
                return redirect('accounts:2fa_login_verify')

            login(request, user)
            next_url = request.GET.get('next', 'events:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'registration/login.html')


def login_2fa_verify_view(request):
    """Verifica código 2FA al iniciar sesión."""
    if request.method == 'POST':
        user_id = request.session.get('2fa_pending_user_id')
        if not user_id:
            return redirect('accounts:login')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            request.session.pop('2fa_pending_user_id', None)
            messages.error(request, 'Sesión inválida. Intenta de nuevo.')
            return redirect('accounts:login')

        profile, _ = UserProfile.objects.get_or_create(user=user)

        # Verificar expiración del código
        if profile.two_factor_sent_at:
            expires_at = profile.two_factor_sent_at + timedelta(minutes=_2FA_CODE_EXPIRY_MINUTES)
            if timezone.now() > expires_at:
                profile.two_factor_secret = None
                profile.two_factor_sent_at = None
                profile.save()
                request.session.pop('2fa_pending_user_id', None)
                messages.error(request, 'El código expiró. Vuelve a iniciar sesión.')
                return redirect('accounts:login')

        code = request.POST.get('code', '').strip()
        if code == profile.two_factor_secret:
            profile.two_factor_secret = None
            profile.two_factor_sent_at = None
            profile.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            del request.session['2fa_pending_user_id']
            messages.success(request, 'Verificación completada.')
            return redirect('events:dashboard')
        else:
            messages.error(request, 'Código incorrecto.')

    return render(request, 'accounts/2fa_login_verify.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def _username_from_email(email):
    """Auto-genera un username único a partir del email."""
    base = re.sub(r'[^a-z0-9_]', '', email.split('@')[0].lower()) or 'user'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"
        n += 1
    return username


def register_view(request):
    if request.user.is_authenticated:
        return redirect('events:dashboard')

    if request.method == 'POST':
        email     = request.POST.get('email', '').strip().lower()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not email:
            messages.error(request, 'El correo electrónico es obligatorio.')
            return render(request, 'registration/register.html')
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Ya existe una cuenta con ese correo.')
            return render(request, 'registration/register.html')
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'registration/register.html')
        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'registration/register.html')

        username = _username_from_email(email)
        user = User.objects.create_user(
            username=username, email=email, password=password1,
        )
        # UserProfile is created automatically by the post_save signal in models.py
        if user.email:
            _send_welcome_email(user)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'¡Bienvenido a Bind, {user.first_name or user.username}!')
        return redirect('events:dashboard')

    return render(request, 'registration/register.html')


# ─── Perfil propio ────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'accounts/profile.html', {
        'profile':    profile,
        'is_admin':   is_bind_admin(request.user),
    })


@login_required
def profile_edit_view(request):
    """Edita el perfil del usuario autenticado."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Datos del User de Django
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name  = request.POST.get('last_name', '').strip()
        request.user.email      = request.POST.get('email', '').strip()

        # Datos del UserProfile
        raw_phone = request.POST.get('phone', '').strip()

        if raw_phone and not re.match(r'^\+?\d{7,15}$', raw_phone):
            messages.error(
                request,
                'Número de teléfono inválido. Usa formato internacional: +573001234567 '
                '(+ seguido de 7 a 15 dígitos, sin espacios ni guiones).'
            )
            return render(request, 'accounts/profile_edit.html', {'profile': profile})

        profile.phone = raw_phone or None
        profile.bio   = request.POST.get('bio', '').strip()

        wants_2fa = request.POST.get('two_factor_enabled') == 'on'
        enabling_2fa = wants_2fa and not profile.two_factor_enabled

        # Si intenta desactivar 2FA desde aquí, permitirlo directamente
        if not wants_2fa and profile.two_factor_enabled:
            profile.two_factor_enabled = False
            profile.two_factor_secret = None
            profile.two_factor_sent_at = None

        # Avatar (archivo)
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']

        request.user.save()
        profile.save()

        # Si quiere activar 2FA, redirigir al flujo de verificación por email
        if enabling_2fa:
            messages.info(request, 'Para activar la verificación en 2 pasos, confirma tu email.')
            return redirect('accounts:2fa_enable')

        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('accounts:profile')

    context = {
        'profile': profile,
        'is_admin': is_bind_admin(request.user),
    }
    return render(request, 'accounts/profile_edit.html', context)


def _generate_2fa_code():
    """Genera código de 6 dígitos."""
    return str(random.randint(100000, 999999))


def _send_welcome_email(user):
    """Envía correo de bienvenida a un usuario recién registrado. Silencia errores de SMTP."""
    name = user.first_name or user.username
    try:
        send_mail(
            subject='¡Bienvenido a BIND!',
            message=(
                f'Hola {name},\n\n'
                'Tu cuenta en BIND ha sido creada exitosamente. '
                'Ya puedes acceder a la plataforma y comenzar a gestionar tus eventos.\n\n'
                '— El equipo de BIND'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


@login_required
def enable_2fa_send(request):
    """Envía código de verificación al email."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not request.user.email:
        messages.error(request, 'Debes tener un email configurado.')
        return redirect('accounts:profile_edit')

    code = _generate_2fa_code()
    profile.two_factor_secret = code
    profile.two_factor_sent_at = timezone.now()
    profile.save()

    try:
        send_mail(
            subject='Tu código de verificación BIND',
            message=f'Hola {request.user.first_name or request.user.username},\n\nTu código de verificación es: {code}\n\nVálido por {_2FA_CODE_EXPIRY_MINUTES} minutos.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
        messages.success(request, 'Código enviado a tu email.')
    except Exception:
        messages.error(request, 'No se pudo enviar el email. Verifica tu configuración SMTP.')

    return redirect('accounts:2fa_verify')


@login_required
def verify_2fa_view(request):
    """Verifica código 2FA."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Verificar expiración del código
        if profile.two_factor_sent_at:
            expires_at = profile.two_factor_sent_at + timedelta(minutes=_2FA_CODE_EXPIRY_MINUTES)
            if timezone.now() > expires_at:
                profile.two_factor_secret = None
                profile.two_factor_sent_at = None
                profile.save()
                messages.error(request, 'El código expiró. Solicita uno nuevo.')
                return redirect('accounts:2fa_enable')

        code = request.POST.get('code', '').strip()
        if code == profile.two_factor_secret:
            profile.two_factor_enabled = True
            profile.two_factor_secret = None
            profile.two_factor_sent_at = None
            profile.save()
            messages.success(request, 'Verificación en 2 pasos activada.')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Código incorrecto.')

    return render(request, 'accounts/2fa_verify.html', {'profile': profile})


@login_required
def disable_2fa_view(request):
    """Desactiva verificación en 2 pasos."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.two_factor_enabled = False
    profile.two_factor_secret = None
    profile.save()
    messages.success(request, 'Verificación en 2 pasos desactivada.')
    return redirect('accounts:profile')


# ─── Administración de usuarios (solo admins) ─────────────────────────────────

@login_required
def user_list_view(request):
    """Lista todos los usuarios del sistema. Solo accesible por admins."""
    if not is_bind_admin(request.user):
        messages.error(request, 'No tienes permiso para acceder a esta sección.')
        return redirect('events:dashboard')

    # Asegurar que todos los usuarios tengan perfil
    for u in User.objects.all():
        UserProfile.objects.get_or_create(user=u)

    users = User.objects.select_related('profile').order_by('date_joined')

    # Búsqueda rápida
    q = request.GET.get('q', '').strip()
    if q:
        users = users.filter(username__icontains=q) | users.filter(email__icontains=q) | \
                users.filter(first_name__icontains=q) | users.filter(last_name__icontains=q)

    context = {
        'users':    users,
        'q':        q,
        'is_admin': True,
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
def user_edit_view(request, pk):
    """Edita el perfil de cualquier usuario. Solo accesible por admins."""
    if not is_bind_admin(request.user):
        messages.error(request, 'No tienes permiso para realizar esta acción.')
        return redirect('events:dashboard')

    target_user    = get_object_or_404(User, pk=pk)
    target_profile, _ = UserProfile.objects.get_or_create(user=target_user)

    if request.method == 'POST':
        # Datos del User de Django
        target_user.first_name = request.POST.get('first_name', '').strip()
        target_user.last_name  = request.POST.get('last_name', '').strip()
        target_user.email      = request.POST.get('email', '').strip()

        # Activar / desactivar cuenta
        target_user.is_active  = request.POST.get('is_active') == 'on'

        # Rol en BIND
        new_role = request.POST.get('role', 'organizer')
        if new_role in dict(UserProfile.ROLE_CHOICES):
            target_profile.role = new_role

        # Protección: no degradar al propio admin que está editando
        if target_user == request.user and new_role != 'admin':
            messages.warning(request, 'No puedes quitarte el rol de administrador a ti mismo.')
            target_profile.role = 'admin'

        target_user.save()
        target_profile.save()

        messages.success(request, f'Usuario "{target_user.username}" actualizado correctamente.')
        return redirect('accounts:user_list')

    context = {
        'target_user':    target_user,
        'target_profile': target_profile,
        'role_choices':   UserProfile.ROLE_CHOICES,
        'is_admin':       True,
    }
    return render(request, 'accounts/user_edit.html', context)


@login_required
def user_delete_view(request, pk):
    """Elimina un usuario. Solo admins. No permite auto-eliminación."""
    if not is_bind_admin(request.user):
        messages.error(request, 'No tienes permiso para realizar esta acción.')
        return redirect('events:dashboard')

    target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta desde aquí.')
        return redirect('accounts:user_list')

    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        messages.success(request, f'Usuario "{username}" eliminado.')
        return redirect('accounts:user_list')

    return render(request, 'accounts/user_confirm_delete.html', {
        'target_user': target_user,
        'is_admin':    True,
    })


# ─── Onboarding tour ──────────────────────────────────────────────────────────

@login_required
@require_POST
def tour_complete_view(request):
    """Marca el onboarding tour como completado para el usuario autenticado."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.onboarding_completed = True
    profile.save(update_fields=['onboarding_completed'])
    return JsonResponse({'ok': True})