from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages

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
            login(request, user)
            UserProfile.objects.get_or_create(user=user)
            next_url = request.GET.get('next', 'events:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'registration/login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('events:dashboard')

    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        email      = request.POST.get('email', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()

        if not username:
            messages.error(request, 'El nombre de usuario es obligatorio.')
            return render(request, 'registration/register.html')
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'registration/register.html')
        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'registration/register.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya está en uso.')
            return render(request, 'registration/register.html')

        user = User.objects.create_user(
            username=username, email=email, password=password1,
            first_name=first_name, last_name=last_name,
        )
        UserProfile.objects.create(user=user)
        login(request, user)
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