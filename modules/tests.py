"""
Suite de tests de endpoints HTTP para la app `modules` de BIND.

Cubre: TaskViewsTest, AttendeeViewsTest, ChecklistViewsTest, BudgetViewsTest
Aspectos testeados por grupo:
  - GET lista y formulario (200 OK, plantilla correcta)
  - POST crear válido (302, objeto creado en DB)
  - POST crear inválido (sin redirect, mensaje de error)
  - POST editar (302, cambios persistidos)
  - POST eliminar (302, objeto ausente en DB)
  - Ownership: acceso con otro usuario → 404
  - Autenticación: sin login → redirect al login
  - Open-redirect: task_toggle_done / budget_item_create con next externo → fallback seguro
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from events.models import Event
from modules.models import (
    Task,
    Attendee,
    Checklist,
    ChecklistItem,
    Budget,
    BudgetItem,
)
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
#  Base
# ─────────────────────────────────────────────────────────────

class ModulesBaseTestCase(TestCase):
    """Fixture mínimo compartido por todos los grupos de tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com', password='pass1234!'
        )
        self.other = User.objects.create_user(
            username='other', email='other@test.com', password='pass1234!'
        )
        self.client.login(username='testuser', password='pass1234!')
        self.event = Event.objects.create(
            name='Test Event', owner=self.user, status='active'
        )
        # Evento que pertenece al otro usuario
        self.other_event = Event.objects.create(
            name='Other Event', owner=self.other, status='active'
        )


# ─────────────────────────────────────────────────────────────
#  TAREAS
# ─────────────────────────────────────────────────────────────

class TaskViewsTest(ModulesBaseTestCase):
    """Tests para task_overview, task_list, task_create, task_edit, task_delete, task_toggle_done."""

    # ── helpers ─────────────────────────────────────────────

    def _create_task(self, title='Tarea de prueba', status='pending', priority='medium'):
        return Task.objects.create(
            event=self.event,
            title=title,
            priority=priority,
            status=status,
        )

    # ── task_overview ────────────────────────────────────────

    def test_task_overview_get_200(self):
        url = reverse('modules:task_overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_task_overview_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse('modules:task_overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])

    def test_task_overview_only_shows_own_tasks(self):
        self._create_task('Mi tarea')
        Task.objects.create(event=self.other_event, title='Ajena', priority='low', status='pending')
        url = reverse('modules:task_overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        task_titles = [t.title for t in response.context['tasks']]
        self.assertIn('Mi tarea', task_titles)
        self.assertNotIn('Ajena', task_titles)

    # ── task_list ────────────────────────────────────────────

    def test_task_list_get_200(self):
        url = reverse('modules:task_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_task_list_ownership_404(self):
        """Otro usuario no puede ver la lista de tareas del evento ajeno."""
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:task_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_task_list_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse('modules:task_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # ── task_create ──────────────────────────────────────────

    def test_task_create_get_200(self):
        url = reverse('modules:task_create', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_task_create_post_valid_creates_task(self):
        url = reverse('modules:task_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {
            'title': 'Nueva Tarea',
            'description': 'Descripción de prueba',
            'priority': 'high',
            'status': 'pending',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(title='Nueva Tarea', event=self.event).exists())

    def test_task_create_post_no_title_does_not_create(self):
        url = reverse('modules:task_create', kwargs={'event_pk': self.event.pk})
        count_before = Task.objects.filter(event=self.event).count()
        response = self.client.post(url, {'title': '', 'priority': 'medium', 'status': 'pending'})
        # No debe redirigir — debe volver a renderizar el formulario
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(Task.objects.filter(event=self.event).count(), count_before)

    def test_task_create_ownership_404(self):
        """Crear tarea en evento ajeno → 404."""
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:task_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {'title': 'Intruso', 'priority': 'low', 'status': 'pending'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Task.objects.filter(title='Intruso').exists())

    # ── task_edit ────────────────────────────────────────────

    def test_task_edit_get_200(self):
        task = self._create_task()
        url = reverse('modules:task_edit', kwargs={'event_pk': self.event.pk, 'pk': task.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_task_edit_post_updates_task(self):
        task = self._create_task(title='Original')
        url = reverse('modules:task_edit', kwargs={'event_pk': self.event.pk, 'pk': task.pk})
        response = self.client.post(url, {
            'title': 'Editada',
            'description': '',
            'priority': 'low',
            'status': 'in_progress',
        })
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Editada')
        self.assertEqual(task.status, 'in_progress')

    def test_task_edit_ownership_404(self):
        task = self._create_task()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:task_edit', kwargs={'event_pk': self.event.pk, 'pk': task.pk})
        response = self.client.post(url, {'title': 'Hack', 'priority': 'low', 'status': 'pending'})
        self.assertEqual(response.status_code, 404)

    # ── task_delete ──────────────────────────────────────────

    def test_task_delete_get_200(self):
        task = self._create_task()
        url = reverse('modules:task_delete', kwargs={'event_pk': self.event.pk, 'pk': task.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_task_delete_post_removes_task(self):
        task = self._create_task()
        pk = task.pk
        url = reverse('modules:task_delete', kwargs={'event_pk': self.event.pk, 'pk': pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=pk).exists())

    def test_task_delete_ownership_404(self):
        task = self._create_task()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:task_delete', kwargs={'event_pk': self.event.pk, 'pk': task.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    # ── task_toggle_done ─────────────────────────────────────

    def test_task_toggle_done_pending_becomes_done(self):
        task = self._create_task(status='pending')
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, 'done')

    def test_task_toggle_done_done_becomes_pending(self):
        task = self._create_task(status='done')
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        self.client.post(url)
        task.refresh_from_db()
        self.assertEqual(task.status, 'pending')

    def test_task_toggle_done_in_progress_becomes_done(self):
        task = self._create_task(status='in_progress')
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        self.client.post(url)
        task.refresh_from_db()
        self.assertEqual(task.status, 'done')

    def test_task_toggle_done_safe_next_redirects(self):
        """next que empieza con / debe redirigir a esa URL."""
        task = self._create_task()
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        safe_next = '/modulos/tareas/'
        response = self.client.post(url, {'next': safe_next})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], safe_next)

    def test_task_toggle_done_open_redirect_blocked(self):
        """next apuntando a dominio externo NO debe redirigir a ese dominio."""
        task = self._create_task()
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        evil = 'https://evil.com/steal'
        response = self.client.post(url, {'next': evil})
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], evil)
        # Debe ir al fallback: task_overview
        self.assertIn('tasks', response['Location'])

    def test_task_toggle_done_open_redirect_double_slash_blocked(self):
        """//evil.com tampoco debe redirigir externamente."""
        task = self._create_task()
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        evil = '//evil.com/phish'
        response = self.client.post(url, {'next': evil})
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], evil)

    def test_task_toggle_done_get_method_forbidden(self):
        """GET en toggle_done debe devolver 403."""
        task = self._create_task()
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_task_toggle_done_ownership_404(self):
        task = self._create_task()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_task_toggle_done_unauthenticated_redirects(self):
        task = self._create_task()
        self.client.logout()
        url = reverse('modules:task_toggle_done', kwargs={'pk': task.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])


# ─────────────────────────────────────────────────────────────
#  ASISTENTES
# ─────────────────────────────────────────────────────────────

class AttendeeViewsTest(ModulesBaseTestCase):
    """Tests para attendee_list, attendee_create, attendee_edit, attendee_delete."""

    def _create_attendee(self, name='Ana Pérez'):
        return Attendee.objects.create(
            event=self.event, name=name, email='ana@test.com', status='pending'
        )

    # ── attendee_list ────────────────────────────────────────

    def test_attendee_list_get_200(self):
        url = reverse('modules:attendee_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_attendee_list_ownership_404(self):
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:attendee_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_attendee_list_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse('modules:attendee_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # ── attendee_create ──────────────────────────────────────

    def test_attendee_create_get_200(self):
        url = reverse('modules:attendee_create', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_attendee_create_post_valid_creates_attendee(self):
        url = reverse('modules:attendee_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {
            'name': 'Carlos López',
            'email': 'carlos@test.com',
            'status': 'confirmed',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Attendee.objects.filter(name='Carlos López', event=self.event).exists()
        )

    def test_attendee_create_post_no_name_does_not_create(self):
        url = reverse('modules:attendee_create', kwargs={'event_pk': self.event.pk})
        count_before = Attendee.objects.filter(event=self.event).count()
        response = self.client.post(url, {'name': '', 'email': 'x@test.com', 'status': 'pending'})
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(Attendee.objects.filter(event=self.event).count(), count_before)

    def test_attendee_create_without_email_creates_attendee(self):
        """El email es opcional; se debe poder crear un asistente sin él."""
        url = reverse('modules:attendee_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {'name': 'Sin Email', 'email': '', 'status': 'pending'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Attendee.objects.filter(name='Sin Email', event=self.event).exists())

    def test_attendee_create_ownership_404(self):
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:attendee_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {'name': 'Hack', 'email': '', 'status': 'pending'})
        self.assertEqual(response.status_code, 404)

    # ── attendee_edit ────────────────────────────────────────

    def test_attendee_edit_get_200(self):
        attendee = self._create_attendee()
        url = reverse('modules:attendee_edit',
                      kwargs={'event_pk': self.event.pk, 'pk': attendee.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_attendee_edit_post_updates_attendee(self):
        attendee = self._create_attendee(name='Original')
        url = reverse('modules:attendee_edit',
                      kwargs={'event_pk': self.event.pk, 'pk': attendee.pk})
        response = self.client.post(url, {
            'name': 'Actualizado',
            'email': 'upd@test.com',
            'status': 'confirmed',
        })
        self.assertEqual(response.status_code, 302)
        attendee.refresh_from_db()
        self.assertEqual(attendee.name, 'Actualizado')
        self.assertEqual(attendee.status, 'confirmed')

    def test_attendee_edit_ownership_404(self):
        attendee = self._create_attendee()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:attendee_edit',
                      kwargs={'event_pk': self.event.pk, 'pk': attendee.pk})
        response = self.client.post(url, {'name': 'Hack', 'email': '', 'status': 'pending'})
        self.assertEqual(response.status_code, 404)

    # ── attendee_delete ──────────────────────────────────────

    def test_attendee_delete_get_200(self):
        attendee = self._create_attendee()
        url = reverse('modules:attendee_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': attendee.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_attendee_delete_post_removes_attendee(self):
        attendee = self._create_attendee()
        pk = attendee.pk
        url = reverse('modules:attendee_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attendee.objects.filter(pk=pk).exists())

    def test_attendee_delete_ownership_404(self):
        attendee = self._create_attendee()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:attendee_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': attendee.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Attendee.objects.filter(pk=attendee.pk).exists())

    def test_attendee_delete_unauthenticated_redirects(self):
        attendee = self._create_attendee()
        self.client.logout()
        url = reverse('modules:attendee_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': attendee.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────────────────────
#  CHECKLISTS
# ─────────────────────────────────────────────────────────────

class ChecklistViewsTest(ModulesBaseTestCase):
    """Tests para checklist_list, checklist_create, checklist_delete,
    checklist_item_create, checklist_item_toggle."""

    def _create_checklist(self, title='Lista de prueba'):
        return Checklist.objects.create(event=self.event, title=title)

    def _create_item(self, checklist, text='Ítem de prueba', is_checked=False):
        return ChecklistItem.objects.create(
            checklist=checklist, text=text, is_checked=is_checked
        )

    # ── checklist_list ───────────────────────────────────────

    def test_checklist_list_get_200(self):
        url = reverse('modules:checklist_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_checklist_list_ownership_404(self):
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:checklist_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_checklist_list_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse('modules:checklist_list', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # ── checklist_create ─────────────────────────────────────

    def test_checklist_create_get_200(self):
        url = reverse('modules:checklist_create', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_checklist_create_post_valid_creates_checklist(self):
        url = reverse('modules:checklist_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {'title': 'Nueva Lista'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Checklist.objects.filter(title='Nueva Lista', event=self.event).exists()
        )

    def test_checklist_create_post_no_title_does_not_create(self):
        url = reverse('modules:checklist_create', kwargs={'event_pk': self.event.pk})
        count_before = Checklist.objects.filter(event=self.event).count()
        response = self.client.post(url, {'title': ''})
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(Checklist.objects.filter(event=self.event).count(), count_before)

    def test_checklist_create_ownership_404(self):
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:checklist_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {'title': 'Hack'})
        self.assertEqual(response.status_code, 404)

    # ── checklist_delete ─────────────────────────────────────

    def test_checklist_delete_get_200(self):
        checklist = self._create_checklist()
        url = reverse('modules:checklist_delete', kwargs={'pk': checklist.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_checklist_delete_post_removes_checklist(self):
        checklist = self._create_checklist()
        pk = checklist.pk
        url = reverse('modules:checklist_delete', kwargs={'pk': pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Checklist.objects.filter(pk=pk).exists())

    def test_checklist_delete_ownership_404(self):
        checklist = self._create_checklist()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:checklist_delete', kwargs={'pk': checklist.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Checklist.objects.filter(pk=checklist.pk).exists())

    def test_checklist_delete_cascades_items(self):
        """Eliminar checklist debe eliminar en cascada sus ítems."""
        checklist = self._create_checklist()
        item = self._create_item(checklist)
        item_pk = item.pk
        url = reverse('modules:checklist_delete', kwargs={'pk': checklist.pk})
        self.client.post(url)
        self.assertFalse(ChecklistItem.objects.filter(pk=item_pk).exists())

    # ── checklist_item_create ────────────────────────────────

    def test_checklist_item_create_get_200(self):
        checklist = self._create_checklist()
        url = reverse('modules:checklist_item_create', kwargs={'pk': checklist.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_checklist_item_create_post_valid_creates_item(self):
        checklist = self._create_checklist()
        url = reverse('modules:checklist_item_create', kwargs={'pk': checklist.pk})
        response = self.client.post(url, {'text': 'Nuevo Ítem'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ChecklistItem.objects.filter(text='Nuevo Ítem', checklist=checklist).exists()
        )

    def test_checklist_item_create_post_empty_text_does_not_create(self):
        """Texto vacío → no crea el ítem (vista redirige pero no persiste)."""
        checklist = self._create_checklist()
        url = reverse('modules:checklist_item_create', kwargs={'pk': checklist.pk})
        count_before = ChecklistItem.objects.filter(checklist=checklist).count()
        self.client.post(url, {'text': ''})
        self.assertEqual(ChecklistItem.objects.filter(checklist=checklist).count(), count_before)

    def test_checklist_item_create_ownership_404(self):
        checklist = self._create_checklist()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:checklist_item_create', kwargs={'pk': checklist.pk})
        response = self.client.post(url, {'text': 'Intruso'})
        self.assertEqual(response.status_code, 404)

    # ── checklist_item_toggle ────────────────────────────────

    def test_checklist_item_toggle_unchecked_becomes_checked(self):
        checklist = self._create_checklist()
        item = self._create_item(checklist, is_checked=False)
        url = reverse('modules:checklist_item_toggle', kwargs={'pk': item.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertTrue(item.is_checked)

    def test_checklist_item_toggle_checked_becomes_unchecked(self):
        checklist = self._create_checklist()
        item = self._create_item(checklist, is_checked=True)
        url = reverse('modules:checklist_item_toggle', kwargs={'pk': item.pk})
        self.client.post(url)
        item.refresh_from_db()
        self.assertFalse(item.is_checked)

    def test_checklist_item_toggle_idempotent_double_call(self):
        """Dos toggles consecutivos deben devolver el ítem al estado original."""
        checklist = self._create_checklist()
        item = self._create_item(checklist, is_checked=False)
        url = reverse('modules:checklist_item_toggle', kwargs={'pk': item.pk})
        self.client.post(url)
        self.client.post(url)
        item.refresh_from_db()
        self.assertFalse(item.is_checked)

    def test_checklist_item_toggle_ownership_404(self):
        checklist = self._create_checklist()
        item = self._create_item(checklist)
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:checklist_item_toggle', kwargs={'pk': item.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    # ── progreso de checklist ────────────────────────────────

    def test_checklist_progress_zero_when_no_items(self):
        checklist = self._create_checklist()
        self.assertEqual(checklist.progress(), 0)

    def test_checklist_progress_100_when_all_checked(self):
        checklist = self._create_checklist()
        self._create_item(checklist, is_checked=True)
        self._create_item(checklist, text='Otro', is_checked=True)
        checklist.refresh_from_db()
        self.assertEqual(checklist.progress(), 100)

    def test_checklist_progress_50_when_half_checked(self):
        checklist = self._create_checklist()
        self._create_item(checklist, is_checked=True)
        self._create_item(checklist, text='Pendiente', is_checked=False)
        checklist.refresh_from_db()
        self.assertEqual(checklist.progress(), 50)


# ─────────────────────────────────────────────────────────────
#  PRESUPUESTO
# ─────────────────────────────────────────────────────────────

class BudgetViewsTest(ModulesBaseTestCase):
    """Tests para budget_detail, budget_item_create, budget_item_delete."""

    def _get_or_create_budget(self):
        budget, _ = Budget.objects.get_or_create(
            event=self.event,
            defaults={'total_budget': 1_000_000, 'currency': 'COP'},
        )
        return budget

    def _create_budget_item(self, name='Catering', amount=200_000):
        budget = self._get_or_create_budget()
        return BudgetItem.objects.create(
            budget=budget, name=name, amount=amount,
            item_type='expense', category='catering',
        )

    # ── budget_detail ────────────────────────────────────────

    def test_budget_detail_get_200(self):
        url = reverse('modules:budget_detail', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_budget_detail_creates_budget_if_missing(self):
        """La primera visita al presupuesto debe crear el objeto Budget."""
        self.assertFalse(Budget.objects.filter(event=self.event).exists())
        url = reverse('modules:budget_detail', kwargs={'event_pk': self.event.pk})
        self.client.get(url)
        self.assertTrue(Budget.objects.filter(event=self.event).exists())

    def test_budget_detail_ownership_404(self):
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:budget_detail', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_budget_detail_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse('modules:budget_detail', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_budget_detail_context_has_budget(self):
        url = reverse('modules:budget_detail', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertIn('budget', response.context)

    # ── budget_item_create ───────────────────────────────────

    def test_budget_item_create_get_200(self):
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_budget_item_create_post_valid_creates_item(self):
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {
            'name': 'Sonido',
            'amount': '500000',
            'item_type': 'expense',
            'category': 'technology',
        })
        self.assertEqual(response.status_code, 302)
        budget = Budget.objects.get(event=self.event)
        self.assertTrue(BudgetItem.objects.filter(name='Sonido', budget=budget).exists())

    def test_budget_item_create_post_income_type(self):
        """Se debe poder registrar un ítem de tipo ingreso."""
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        self.client.post(url, {
            'name': 'Patrocinio',
            'amount': '2000000',
            'item_type': 'income',
            'category': 'other',
        })
        budget = Budget.objects.get(event=self.event)
        self.assertTrue(
            BudgetItem.objects.filter(name='Patrocinio', item_type='income', budget=budget).exists()
        )

    def test_budget_item_create_post_no_name_does_not_create(self):
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        count_before = BudgetItem.objects.count()
        self.client.post(url, {'name': '', 'amount': '1000', 'item_type': 'expense', 'category': 'other'})
        self.assertEqual(BudgetItem.objects.count(), count_before)

    def test_budget_item_create_post_invalid_amount_does_not_create(self):
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        count_before = BudgetItem.objects.count()
        self.client.post(url, {'name': 'Item inválido', 'amount': 'not-a-number',
                               'item_type': 'expense', 'category': 'other'})
        self.assertEqual(BudgetItem.objects.count(), count_before)

    def test_budget_item_create_ownership_404(self):
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        response = self.client.post(url, {'name': 'Hack', 'amount': '100',
                                          'item_type': 'expense', 'category': 'other'})
        self.assertEqual(response.status_code, 404)

    def test_budget_item_create_safe_next_redirects(self):
        """next que empieza con / debe redirigir a esa URL."""
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        safe_next = '/modulos/tareas/'
        response = self.client.post(url, {
            'name': 'Item con next',
            'amount': '300',
            'item_type': 'expense',
            'category': 'other',
            'next': safe_next,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], safe_next)

    def test_budget_item_create_open_redirect_blocked(self):
        """next externo NO debe producir redirect a ese dominio."""
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        evil = 'https://evil.com/steal'
        response = self.client.post(url, {
            'name': 'Item redirigido',
            'amount': '100',
            'item_type': 'expense',
            'category': 'other',
            'next': evil,
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], evil)
        self.assertNotIn('evil.com', response['Location'])

    def test_budget_item_create_open_redirect_no_slash_blocked(self):
        """next sin slash inicial tampoco debe redirigir al destino."""
        url = reverse('modules:budget_item_create', kwargs={'event_pk': self.event.pk})
        evil = 'evil.com/steal'
        response = self.client.post(url, {
            'name': 'Item redirigido 2',
            'amount': '50',
            'item_type': 'expense',
            'category': 'other',
            'next': evil,
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], evil)

    # ── budget_item_delete ───────────────────────────────────

    def test_budget_item_delete_post_removes_item(self):
        item = self._create_budget_item()
        pk = item.pk
        url = reverse('modules:budget_item_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BudgetItem.objects.filter(pk=pk).exists())

    def test_budget_item_delete_ownership_404(self):
        item = self._create_budget_item()
        self.client.logout()
        self.client.login(username='other', password='pass1234!')
        url = reverse('modules:budget_item_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': item.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(BudgetItem.objects.filter(pk=item.pk).exists())

    def test_budget_item_delete_unauthenticated_redirects(self):
        item = self._create_budget_item()
        self.client.logout()
        url = reverse('modules:budget_item_delete',
                      kwargs={'event_pk': self.event.pk, 'pk': item.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])

    # ── propiedades calculadas del Budget ────────────────────

    def test_budget_total_spent_reflects_items(self):
        budget = self._get_or_create_budget()
        BudgetItem.objects.create(budget=budget, name='A', amount=300_000,
                                   item_type='expense', category='other')
        BudgetItem.objects.create(budget=budget, name='B', amount=200_000,
                                   item_type='expense', category='other')
        self.assertEqual(budget.total_spent, 500_000)

    def test_budget_remaining_reflects_items(self):
        budget = self._get_or_create_budget()
        # total_budget = 1_000_000 creado en _get_or_create_budget
        BudgetItem.objects.create(budget=budget, name='Gasto', amount=400_000,
                                   item_type='expense', category='venue')
        self.assertEqual(budget.remaining, 600_000)

    def test_budget_total_spent_zero_when_no_items(self):
        budget = self._get_or_create_budget()
        self.assertEqual(budget.total_spent, 0)

    def test_budget_usage_percentage_calculated_correctly(self):
        budget = self._get_or_create_budget()
        # total_budget = 1_000_000
        BudgetItem.objects.create(budget=budget, name='Mitad', amount=500_000,
                                   item_type='expense', category='other')
        self.assertEqual(budget.usage_percentage, 50)
