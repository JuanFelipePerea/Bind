"""
Suite de tests de endpoints HTTP para la app 'accounts' de BIND.

Cobertura:
  - IndexViewTest          → GET anónimo / GET autenticado
  - LoginViewTest          → GET, POST válido, POST inválido, ya autenticado
  - LogoutViewTest         → GET autenticado / GET anónimo
  - RegisterViewTest       → GET, POST válido, email duplicado, passwords distintas,
                             password corta, email vacío, ya autenticado
  - ProfileViewTest        → GET sin login, GET con login
  - ProfileEditViewTest    → GET sin login, GET con login, POST válido,
                             teléfono inválido, teléfono vacío permitido
  - TwoFactorTest          → disable_2fa POST autenticado, GET → 405,
                             GET sin login → redirect
  - AdminViewsTest         → user_list (admin/no-admin), user_edit (admin/no-admin/auto-demotion),
                             user_delete (admin/no-admin/auto-eliminación/GET)
  - TourTest               → POST autenticado, GET → 405, sin login → redirect

Ejecutar:
  python manage.py test accounts --verbosity=2
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_organizer(username, email, password='pass1234!'):
    """Crea un usuario con rol 'organizer' (default del signal)."""
    user = User.objects.create_user(username=username, email=email, password=password)
    # El signal post_save crea el perfil automáticamente; nos aseguramos de que exista
    UserProfile.objects.get_or_create(user=user)
    return user


def make_admin(username, email, password='pass1234!'):
    """Crea un usuario con rol 'admin' en su UserProfile."""
    user = make_organizer(username, email, password)
    profile = UserProfile.objects.get(user=user)
    profile.role = 'admin'
    profile.save()
    return user


# ---------------------------------------------------------------------------
# 1. IndexViewTest
# ---------------------------------------------------------------------------

class IndexViewTest(TestCase):
    """accounts:index — landing pública / redirección dashboard."""

    def setUp(self):
        self.url = reverse('accounts:index')
        self.user = make_organizer('organizer1', 'organizer1@test.com')

    def test_get_anonymous_renders_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_anonymous_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'accounts/index.html')

    def test_get_authenticated_redirects_to_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_get_authenticated_does_not_render_landing(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# 2. LoginViewTest
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoginViewTest(TestCase):
    """accounts:login — formulario de autenticación."""

    def setUp(self):
        self.url = reverse('accounts:login')
        self.user = make_organizer('loginuser', 'login@test.com', 'pass1234!')

    def test_get_anonymous_renders_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_anonymous_uses_login_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_get_already_authenticated_redirects_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_post_valid_credentials_redirects_dashboard(self):
        response = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'pass1234!',
        })
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_post_valid_credentials_logs_user_in(self):
        self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'pass1234!',
        })
        # Si el usuario está autenticado, el índice debería redirigir al dashboard
        response = self.client.get(reverse('accounts:index'))
        self.assertEqual(response.status_code, 302)

    def test_post_wrong_password_returns_200(self):
        response = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_wrong_password_shows_error_message(self):
        response = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'wrongpassword',
        })
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('incorrectos' in str(m) or 'incorrecto' in str(m).lower() for m in messages_list),
            "Debería mostrar mensaje de error con credenciales inválidas."
        )

    def test_post_nonexistent_user_returns_200(self):
        response = self.client.post(self.url, {
            'username': 'noexiste',
            'password': 'pass1234!',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_next_param_respected_after_login(self):
        response = self.client.post(
            self.url + '?next=/accounts/profile/',
            {'username': 'loginuser', 'password': 'pass1234!'},
        )
        self.assertRedirects(response, '/accounts/profile/', fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# 3. LogoutViewTest
# ---------------------------------------------------------------------------

class LogoutViewTest(TestCase):
    """accounts:logout — cierre de sesión."""

    def setUp(self):
        self.url = reverse('accounts:logout')
        self.user = make_organizer('logoutuser', 'logout@test.com')

    def test_get_authenticated_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('accounts:login'), fetch_redirect_response=False)

    def test_get_anonymous_also_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('accounts:login'), fetch_redirect_response=False)

    def test_get_authenticated_actually_logs_out(self):
        self.client.force_login(self.user)
        self.client.get(self.url)
        # Después del logout el perfil debería requerir login
        response = self.client.get(reverse('accounts:profile'))
        self.assertNotEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# 4. RegisterViewTest
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegisterViewTest(TestCase):
    """accounts:register — creación de cuenta."""

    def setUp(self):
        self.url = reverse('accounts:register')

    def test_get_anonymous_renders_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_anonymous_uses_register_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'registration/register.html')

    def test_get_already_authenticated_redirects_dashboard(self):
        user = make_organizer('already', 'already@test.com')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_post_valid_data_creates_user(self):
        self.client.post(self.url, {
            'email': 'nuevo@test.com',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        self.assertTrue(User.objects.filter(email='nuevo@test.com').exists())

    def test_post_valid_data_creates_user_profile(self):
        self.client.post(self.url, {
            'email': 'perfil@test.com',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        user = User.objects.get(email='perfil@test.com')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_post_valid_data_redirects_dashboard(self):
        response = self.client.post(self.url, {
            'email': 'redirect@test.com',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_post_valid_data_logs_user_in(self):
        self.client.post(self.url, {
            'email': 'loggedin@test.com',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        # Si el usuario quedó autenticado, el índice redirigirá al dashboard
        response = self.client.get(reverse('accounts:index'))
        self.assertEqual(response.status_code, 302)

    def test_post_duplicate_email_returns_200(self):
        make_organizer('existente', 'dup@test.com')
        response = self.client.post(self.url, {
            'email': 'dup@test.com',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_duplicate_email_shows_error(self):
        make_organizer('existente2', 'dup2@test.com')
        response = self.client.post(self.url, {
            'email': 'dup2@test.com',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('cuenta' in str(m).lower() or 'correo' in str(m).lower() for m in messages_list)
        )

    def test_post_passwords_mismatch_returns_200(self):
        response = self.client.post(self.url, {
            'email': 'mismatch@test.com',
            'password1': 'superpass123',
            'password2': 'different123',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_passwords_mismatch_shows_error(self):
        response = self.client.post(self.url, {
            'email': 'mismatch2@test.com',
            'password1': 'superpass123',
            'password2': 'different123',
        })
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('coinciden' in str(m).lower() for m in messages_list)
        )

    def test_post_short_password_returns_200(self):
        response = self.client.post(self.url, {
            'email': 'short@test.com',
            'password1': 'abc',
            'password2': 'abc',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_short_password_shows_error(self):
        response = self.client.post(self.url, {
            'email': 'short2@test.com',
            'password1': 'abc',
            'password2': 'abc',
        })
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('8' in str(m) or 'caracteres' in str(m).lower() for m in messages_list)
        )

    def test_post_empty_email_returns_200(self):
        response = self.client.post(self.url, {
            'email': '',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_empty_email_shows_error(self):
        response = self.client.post(self.url, {
            'email': '',
            'password1': 'superpass123',
            'password2': 'superpass123',
        })
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('correo' in str(m).lower() or 'email' in str(m).lower() for m in messages_list)
        )


# ---------------------------------------------------------------------------
# 5. ProfileViewTest
# ---------------------------------------------------------------------------

class ProfileViewTest(TestCase):
    """accounts:profile — vista del perfil propio."""

    def setUp(self):
        self.url = reverse('accounts:profile')
        self.user = make_organizer('profuser', 'profuser@test.com')

    def test_get_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_get_authenticated_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_authenticated_uses_profile_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'accounts/profile.html')

    def test_get_authenticated_has_profile_in_context(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn('profile', response.context)


# ---------------------------------------------------------------------------
# 6. ProfileEditViewTest
# ---------------------------------------------------------------------------

class ProfileEditViewTest(TestCase):
    """accounts:profile_edit — edición del perfil propio."""

    def setUp(self):
        self.url = reverse('accounts:profile_edit')
        self.user = make_organizer('edituser', 'edit@test.com')

    def test_get_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_get_authenticated_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_authenticated_uses_correct_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'accounts/profile_edit.html')

    def test_post_valid_data_updates_user_fields(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'email': 'nuevo@edit.com',
            'phone': '',
            'bio': '',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Juan')
        self.assertEqual(self.user.last_name, 'Pérez')

    def test_post_valid_data_redirects_to_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'first_name': 'Ana',
            'last_name': 'García',
            'email': 'ana@edit.com',
            'phone': '',
            'bio': 'Hola',
        })
        self.assertRedirects(response, reverse('accounts:profile'), fetch_redirect_response=False)

    def test_post_valid_phone_is_saved(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': self.user.email,
            'phone': '+573001234567',
            'bio': '',
        })
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.phone, '+573001234567')

    def test_post_invalid_phone_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': self.user.email,
            'phone': 'abc-invalid',
            'bio': '',
        })
        self.assertEqual(response.status_code, 200)

    def test_post_invalid_phone_shows_error_message(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': self.user.email,
            'phone': '123',
            'bio': '',
        })
        messages_list = list(response.context['messages'])
        self.assertTrue(
            any('teléfono' in str(m).lower() or 'inválido' in str(m).lower() for m in messages_list)
        )

    def test_post_empty_phone_saves_null(self):
        self.client.force_login(self.user)
        profile = UserProfile.objects.get(user=self.user)
        profile.phone = '+573001234567'
        profile.save()

        self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': self.user.email,
            'phone': '',
            'bio': '',
        })
        profile.refresh_from_db()
        self.assertIsNone(profile.phone)

    def test_post_bio_is_saved(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': self.user.email,
            'phone': '',
            'bio': 'Mi descripción de prueba.',
        })
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.bio, 'Mi descripción de prueba.')


# ---------------------------------------------------------------------------
# 7. TwoFactorTest
# ---------------------------------------------------------------------------

class TwoFactorTest(TestCase):
    """accounts:2fa_disable — desactivación de 2FA."""

    def setUp(self):
        self.url = reverse('accounts:2fa_disable')
        self.user = make_organizer('tfauser', 'tfa@test.com')
        profile = UserProfile.objects.get(user=self.user)
        profile.two_factor_enabled = True
        profile.two_factor_secret = '123456'
        profile.save()

    def test_post_authenticated_disables_2fa(self):
        self.client.force_login(self.user)
        self.client.post(self.url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertFalse(profile.two_factor_enabled)

    def test_post_authenticated_clears_secret(self):
        self.client.force_login(self.user)
        self.client.post(self.url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNone(profile.two_factor_secret)

    def test_post_authenticated_redirects_to_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('accounts:profile'), fetch_redirect_response=False)

    def test_get_authenticated_returns_405(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post_anonymous_redirects_to_login(self):
        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_get_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        # Debe redirigir al login (login_required tiene prioridad sobre require_POST)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])


# ---------------------------------------------------------------------------
# 8. AdminViewsTest
# ---------------------------------------------------------------------------

class AdminViewsTest(TestCase):
    """
    accounts:user_list, user_edit, user_delete
    Sólo accesibles para usuarios con role='admin'.
    """

    def setUp(self):
        self.admin = make_admin('admin_u', 'admin@test.com')
        self.user = make_organizer('org_u', 'org@test.com')
        self.target = make_organizer('target_u', 'target@test.com')

    # ── user_list ──────────────────────────────────────────────────────────

    def test_user_list_anonymous_redirects_login(self):
        url = reverse('accounts:user_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_user_list_non_admin_redirects_dashboard(self):
        self.client.force_login(self.user)
        url = reverse('accounts:user_list')
        response = self.client.get(url)
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_user_list_admin_returns_200(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_user_list_admin_uses_correct_template(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_list')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'accounts/user_list.html')

    def test_user_list_search_filters_results(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_list') + '?q=target'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ── user_edit ──────────────────────────────────────────────────────────

    def test_user_edit_anonymous_redirects_login(self):
        url = reverse('accounts:user_edit', kwargs={'pk': self.target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_user_edit_non_admin_redirects_dashboard(self):
        self.client.force_login(self.user)
        url = reverse('accounts:user_edit', kwargs={'pk': self.target.pk})
        response = self.client.get(url)
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_user_edit_admin_get_returns_200(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_edit', kwargs={'pk': self.target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_user_edit_admin_post_updates_user(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_edit', kwargs={'pk': self.target.pk})
        self.client.post(url, {
            'first_name': 'Nuevo',
            'last_name': 'Nombre',
            'email': self.target.email,
            'is_active': 'on',
            'role': 'organizer',
        })
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, 'Nuevo')

    def test_user_edit_admin_post_redirects_user_list(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_edit', kwargs={'pk': self.target.pk})
        response = self.client.post(url, {
            'first_name': 'Test',
            'last_name': 'Edit',
            'email': self.target.email,
            'is_active': 'on',
            'role': 'organizer',
        })
        self.assertRedirects(response, reverse('accounts:user_list'), fetch_redirect_response=False)

    def test_user_edit_admin_cannot_demote_self(self):
        """El admin no puede quitarse el rol 'admin' a sí mismo."""
        self.client.force_login(self.admin)
        url = reverse('accounts:user_edit', kwargs={'pk': self.admin.pk})
        self.client.post(url, {
            'first_name': '',
            'last_name': '',
            'email': self.admin.email,
            'is_active': 'on',
            'role': 'organizer',  # intenta degradarse
        })
        profile = UserProfile.objects.get(user=self.admin)
        self.assertEqual(profile.role, 'admin')

    def test_user_edit_nonexistent_user_returns_404(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_edit', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # ── user_delete ────────────────────────────────────────────────────────

    def test_user_delete_anonymous_redirects_login(self):
        url = reverse('accounts:user_delete', kwargs={'pk': self.target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_user_delete_non_admin_redirects_dashboard(self):
        self.client.force_login(self.user)
        url = reverse('accounts:user_delete', kwargs={'pk': self.target.pk})
        response = self.client.get(url)
        self.assertRedirects(response, reverse('events:dashboard'), fetch_redirect_response=False)

    def test_user_delete_admin_get_returns_200(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_delete', kwargs={'pk': self.target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_user_delete_admin_post_deletes_user(self):
        self.client.force_login(self.admin)
        target_pk = self.target.pk
        url = reverse('accounts:user_delete', kwargs={'pk': target_pk})
        self.client.post(url)
        self.assertFalse(User.objects.filter(pk=target_pk).exists())

    def test_user_delete_admin_post_redirects_user_list(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_delete', kwargs={'pk': self.target.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('accounts:user_list'), fetch_redirect_response=False)

    def test_user_delete_self_is_prevented(self):
        """El admin no puede eliminarse a sí mismo."""
        self.client.force_login(self.admin)
        url = reverse('accounts:user_delete', kwargs={'pk': self.admin.pk})
        response = self.client.post(url)
        # Debe redirigir al user_list con mensaje de error, sin borrar la cuenta
        self.assertRedirects(response, reverse('accounts:user_list'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_user_delete_nonexistent_returns_404(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:user_delete', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# 9. TourTest
# ---------------------------------------------------------------------------

class TourTest(TestCase):
    """accounts:tour_complete — marcar el tour de onboarding como completado."""

    def setUp(self):
        self.url = reverse('accounts:tour_complete')
        self.user = make_organizer('touruser', 'tour@test.com')

    def test_post_authenticated_marks_onboarding_completed(self):
        self.client.force_login(self.user)
        self.client.post(self.url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.onboarding_completed)

    def test_post_authenticated_returns_json_ok(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('ok'))

    def test_post_authenticated_content_type_is_json(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertIn('application/json', response.get('Content-Type', ''))

    def test_get_authenticated_returns_405(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post_anonymous_redirects_to_login(self):
        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_get_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_onboarding_idempotent_second_call(self):
        """Llamar tour_complete dos veces no debe romper nada."""
        self.client.force_login(self.user)
        self.client.post(self.url)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.onboarding_completed)
