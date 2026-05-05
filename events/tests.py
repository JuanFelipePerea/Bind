from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from events.models import Event, EventAlert, EngineMetrics
from events.engine.context import build_event_context
from events.engine.scorer import score_event, EventScore
from events.engine.decisions import derive_decisions


class EventScoreTest(TestCase):
    """Tests para el dataclass EventScore y sus propiedades."""

    def test_health_score_is_complement_of_risk(self):
        s = EventScore(risk_level=30)
        self.assertEqual(s.health_score, 70)

    def test_health_score_clamped_at_zero(self):
        s = EventScore(risk_level=100)
        self.assertEqual(s.health_score, 0)

    def test_health_labels(self):
        self.assertEqual(EventScore(risk_level=10).health_label, 'excellent')
        self.assertEqual(EventScore(risk_level=35).health_label, 'good')
        self.assertEqual(EventScore(risk_level=55).health_label, 'at_risk')
        self.assertEqual(EventScore(risk_level=70).health_label, 'critical')

    def test_risk_labels(self):
        self.assertEqual(EventScore(risk_level=10).risk_label, 'low')
        self.assertEqual(EventScore(risk_level=35).risk_label, 'medium')
        self.assertEqual(EventScore(risk_level=55).risk_label, 'high')
        self.assertEqual(EventScore(risk_level=75).risk_label, 'critical')

    def test_momentum_defaults_to_stable(self):
        s = EventScore(risk_level=20)
        self.assertEqual(s.momentum_label, 'stable')

    def test_momentum_custom(self):
        s = EventScore(risk_level=20, momentum='accelerating')
        self.assertEqual(s.momentum_label, 'accelerating')


class EngineContextTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test1234')
        self.event = Event.objects.create(
            name='Test Event',
            owner=self.user,
            status='active',
            start_date=timezone.now() + timedelta(days=10),
        )

    def test_context_builds_without_error(self):
        ctx = build_event_context(self.event)
        self.assertIsNotNone(ctx)
        self.assertIs(ctx.event, self.event)

    def test_context_task_total_is_zero_for_new_event(self):
        ctx = build_event_context(self.event)
        self.assertEqual(ctx.task_total, 0)

    def test_context_days_until_calculated_correctly(self):
        ctx = build_event_context(self.event)
        self.assertIsNotNone(ctx.days_until)
        self.assertGreater(ctx.days_until, 0)

    def test_context_no_start_date(self):
        self.event.start_date = None
        self.event.save()
        ctx = build_event_context(self.event)
        self.assertIsNone(ctx.days_until)
        self.assertFalse(ctx.has_start_date)


class ScorerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='scorer_user', password='test1234')
        self.event = Event.objects.create(
            name='Scorer Test',
            owner=self.user,
            status='active',
            start_date=timezone.now() + timedelta(days=10),
        )

    def test_score_returns_event_score_object(self):
        ctx = build_event_context(self.event)
        score = score_event(ctx)
        self.assertIsInstance(score, EventScore)

    def test_health_score_between_0_and_100(self):
        ctx = build_event_context(self.event)
        score = score_event(ctx)
        self.assertGreaterEqual(score.health_score, 0)
        self.assertLessEqual(score.health_score, 100)

    def test_risk_increases_for_imminent_event_with_high_priority_tasks(self):
        from modules.models import Task
        self.event.start_date = timezone.now() + timedelta(days=2)
        self.event.save()
        for i in range(3):
            Task.objects.create(
                event=self.event,
                title=f'Tarea urgente {i}',
                priority='high',
                status='pending',
            )
        ctx = build_event_context(self.event)
        score = score_event(ctx)
        # Evento en 2 dias (+40) + high pending tasks (+30) = 70+
        self.assertGreaterEqual(score.risk_level, 60)
        self.assertIn(score.risk_label, ('critical', 'high'))

    def test_low_risk_for_distant_event_with_no_tasks(self):
        self.event.start_date = timezone.now() + timedelta(days=90)
        self.event.save()
        ctx = build_event_context(self.event)
        score = score_event(ctx)
        self.assertEqual(score.risk_level, 0)
        self.assertEqual(score.risk_label, 'low')

    def test_stalled_momentum_label(self):
        from modules.models import Task
        task = Task.objects.create(event=self.event, title='Old task', status='pending')
        Task.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(days=20)
        )
        ctx = build_event_context(self.event)
        self.assertGreater(ctx.last_activity_days, 14)
        score = score_event(ctx)
        self.assertEqual(score.momentum_label, 'stalled')


class DecisionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dec_user', password='test1234')

    def test_derive_decisions_is_callable(self):
        self.assertTrue(callable(derive_decisions))

    def test_no_decisions_for_safe_event(self):
        from modules.models import Task
        event = Event.objects.create(
            name='Safe Event',
            owner=self.user,
            status='active',
            start_date=timezone.now() + timedelta(days=30),
        )
        # Agregar una tarea completada para que no dispare la regla no-tasks
        Task.objects.create(event=event, title='Tarea hecha', status='done')
        ctx = build_event_context(event)
        score = score_event(ctx)
        decisions = derive_decisions(ctx, score)
        self.assertEqual(len(decisions), 0)

    def test_critical_decision_for_imminent_event_with_high_tasks(self):
        from modules.models import Task
        event = Event.objects.create(
            name='Imminent Event',
            owner=self.user,
            status='active',
            start_date=timezone.now() + timedelta(days=2),
        )
        Task.objects.create(
            event=event, title='Alta prioridad', priority='high', status='pending'
        )
        ctx = build_event_context(event)
        score = score_event(ctx)
        decisions = derive_decisions(ctx, score)
        critical = [d for d in decisions if d.severity == 'critical']
        self.assertGreater(len(critical), 0)


class RunEngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='eng_user', password='test1234')

    def test_run_engine_returns_expected_keys(self):
        from events.engine import run_engine_for_user
        Event.objects.create(
            name='Test', owner=self.user, status='active',
            start_date=timezone.now() + timedelta(days=5),
        )
        result = run_engine_for_user(self.user)
        self.assertIn('event_scores', result)
        self.assertIn('event_contexts', result)
        self.assertIn('all_decisions', result)
        self.assertIn('dashboard_summary', result)

    def test_dashboard_summary_has_expected_keys(self):
        from events.engine import run_engine_for_user
        result = run_engine_for_user(self.user)
        summary = result['dashboard_summary']
        self.assertIn('critical_count', summary)
        self.assertIn('events_at_risk', summary)
        self.assertIn('events_on_track', summary)
        self.assertIn('needs_attention', summary)

    def test_event_scores_keyed_by_pk(self):
        from events.engine import run_engine_for_user
        event = Event.objects.create(
            name='Test', owner=self.user, status='active',
            start_date=timezone.now() + timedelta(days=10),
        )
        result = run_engine_for_user(self.user)
        self.assertIn(event.pk, result['event_scores'])
        self.assertIsInstance(result['event_scores'][event.pk], EventScore)


# ─────────────────────────────────────────────────────────────────────────────
#  ETAPA 3 — Tests
# ─────────────────────────────────────────────────────────────────────────────

class BudgetAlertTest(TestCase):
    """Reglas de presupuesto en alert_engine."""

    def setUp(self):
        self.user = User.objects.create_user(username='budget_user', password='test1234')
        self.event = Event.objects.create(
            name='Evento Presupuesto', owner=self.user, status='active',
            start_date=timezone.now() + timedelta(days=20),
        )

    def _make_budget(self, total, spent_amounts):
        from modules.models import Budget, BudgetItem
        budget = Budget.objects.create(event=self.event, total_budget=total)
        for amount in spent_amounts:
            BudgetItem.objects.create(budget=budget, name=f'Gasto {amount}', amount=amount)
        return budget

    def test_budget_warning_alert_at_80_percent(self):
        """usage >= 80% genera alerta warning."""
        from events.services.alert_engine import run_alert_engine
        self._make_budget(total=1000, spent_amounts=[850])
        run_alert_engine(self.user)
        alert = EventAlert.objects.filter(
            event=self.event, alert_type='budget', severity='warning'
        ).first()
        self.assertIsNotNone(alert)
        self.assertIn('budget-warning', alert.alert_key)

    def test_budget_critical_alert_at_100_percent(self):
        """usage >= 100% genera alerta critical."""
        from events.services.alert_engine import run_alert_engine
        self._make_budget(total=1000, spent_amounts=[1100])
        run_alert_engine(self.user)
        alert = EventAlert.objects.filter(
            event=self.event, alert_type='budget', severity='critical'
        ).first()
        self.assertIsNotNone(alert)
        self.assertIn('budget-critical', alert.alert_key)

    def test_budget_suggest_alert_no_budget_many_tasks(self):
        """Sin presupuesto y con más de 3 tareas → info."""
        from modules.models import Task
        from events.services.alert_engine import run_alert_engine
        for i in range(4):
            Task.objects.create(event=self.event, title=f'Tarea {i}', status='pending')
        run_alert_engine(self.user)
        alert = EventAlert.objects.filter(
            event=self.event, alert_type='budget', severity='info'
        ).first()
        self.assertIsNotNone(alert)
        self.assertIn('budget-suggest', alert.alert_key)

    def test_no_budget_alert_below_threshold(self):
        """Sin presupuesto y con <=3 tareas NO genera alerta."""
        from modules.models import Task
        from events.services.alert_engine import run_alert_engine
        Task.objects.create(event=self.event, title='Solo una tarea', status='pending')
        run_alert_engine(self.user)
        alert = EventAlert.objects.filter(
            event=self.event, alert_type='budget'
        ).first()
        self.assertIsNone(alert)


class DecisionsCompleteTest(TestCase):
    """Las 5 reglas nuevas de decisions.py generan Decision con severity y alert_key correctos."""

    def setUp(self):
        self.user = User.objects.create_user(username='dec2_user', password='test1234')

    def _make_event(self, **kwargs):
        defaults = dict(owner=self.user, status='active')
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def test_stalled_warning_decision(self):
        """Sin actividad 7+ días y evento en <=30 días → warning stalled."""
        from modules.models import Task
        event = self._make_event(
            name='Stalled', start_date=timezone.now() + timedelta(days=15)
        )
        task = Task.objects.create(event=event, title='Tarea vieja', status='pending')
        Task.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(days=10)
        )
        ctx = build_event_context(event)
        decisions = derive_decisions(ctx, score_event(ctx))
        stalled = [d for d in decisions if d.alert_key.startswith('stalled-')]
        self.assertGreater(len(stalled), 0)
        self.assertEqual(stalled[0].severity, 'warning')

    def test_overdue_tasks_warning_decision(self):
        """3+ tareas vencidas → warning overdue-tasks."""
        from modules.models import Task
        event = self._make_event(
            name='Overdue', start_date=timezone.now() + timedelta(days=20)
        )
        past = timezone.now().date() - timedelta(days=5)
        for i in range(3):
            Task.objects.create(
                event=event, title=f'Vencida {i}',
                status='pending', due_date=past
            )
        ctx = build_event_context(event)
        decisions = derive_decisions(ctx, score_event(ctx))
        overdue = [d for d in decisions if d.alert_key.startswith('overdue-tasks-')]
        self.assertGreater(len(overdue), 0)
        self.assertEqual(overdue[0].severity, 'warning')

    def test_pending_attendees_warning_decision(self):
        """Asistentes pendientes y evento en <=7 días → warning pending-attendees."""
        from modules.models import Attendee
        event = self._make_event(
            name='Attendees', start_date=timezone.now() + timedelta(days=5)
        )
        Attendee.objects.create(event=event, name='Juan', email='juan@test.com', status='pending')
        ctx = build_event_context(event)
        decisions = derive_decisions(ctx, score_event(ctx))
        att = [d for d in decisions if d.alert_key.startswith('pending-attendees-')]
        self.assertGreater(len(att), 0)
        self.assertEqual(att[0].severity, 'warning')

    def test_no_date_info_decision(self):
        """Sin fecha y con >5 tareas → info no-date."""
        from modules.models import Task
        event = self._make_event(name='NoDate', start_date=None)
        for i in range(6):
            Task.objects.create(event=event, title=f'T{i}', status='pending')
        ctx = build_event_context(event)
        decisions = derive_decisions(ctx, score_event(ctx))
        nodate = [d for d in decisions if d.alert_key.startswith('no-date-')]
        self.assertGreater(len(nodate), 0)
        self.assertEqual(nodate[0].severity, 'info')

    def test_no_tasks_info_decision(self):
        """Evento activo sin tareas → info no-tasks."""
        event = self._make_event(name='NoTasks', start_date=None)
        ctx = build_event_context(event)
        decisions = derive_decisions(ctx, score_event(ctx))
        notasks = [d for d in decisions if d.alert_key.startswith('no-tasks-')]
        self.assertGreater(len(notasks), 0)
        self.assertEqual(notasks[0].severity, 'info')


class LearningTest(TestCase):
    """analyze_user_patterns() con EngineMetrics reales retorna estructura esperada."""

    def setUp(self):
        self.user = User.objects.create_user(username='learn_user', password='test1234')
        self.event = Event.objects.create(
            name='Evento Learning', owner=self.user, status='active'
        )

    def _create_metric(self, decision_type, user_acted, action='test'):
        EngineMetrics.objects.create(
            decision_key=f'{decision_type}-{self.event.pk}-{action}-{user_acted}',
            decision_type=decision_type,
            event=self.event,
            user=self.user,
            user_acted=user_acted,
            action_taken=action,
        )

    def test_returns_expected_keys(self):
        from events.engine.learning import analyze_user_patterns
        result = analyze_user_patterns(self.user)
        self.assertIn('avg_action_rate', result)
        self.assertIn('by_type', result)
        self.assertIn('low_follow_types', result)
        self.assertIn('high_follow_types', result)

    def test_none_when_no_metrics(self):
        from events.engine.learning import analyze_user_patterns
        result = analyze_user_patterns(self.user)
        self.assertIsNone(result['avg_action_rate'])

    def test_action_rate_computed_correctly(self):
        from events.engine.learning import analyze_user_patterns
        for i in range(3):
            self._create_metric('deadline', True, f'act{i}')
        self._create_metric('deadline', False, 'dis')
        result = analyze_user_patterns(self.user)
        self.assertAlmostEqual(result['avg_action_rate'], 0.75)

    def test_low_follow_type_detected(self):
        from events.engine.learning import analyze_user_patterns
        for i in range(5):
            self._create_metric('stalled', False, f'ign{i}')
        result = analyze_user_patterns(self.user)
        self.assertIn('stalled', result['low_follow_types'])

    def test_high_follow_type_detected(self):
        from events.engine.learning import analyze_user_patterns
        for i in range(5):
            self._create_metric('deadline', True, f'act{i}')
        result = analyze_user_patterns(self.user)
        self.assertIn('deadline', result['high_follow_types'])

    def test_personalized_thresholds_stalled_relaxed(self):
        from events.engine.learning import get_personalized_thresholds
        for i in range(4):
            self._create_metric('stalled', False, f'ign{i}')
        thresholds = get_personalized_thresholds(self.user)
        self.assertGreater(thresholds['stalled_days'], 7)


class PrioritizeTasksRichTest(TestCase):
    """prioritize_tasks() retorna objetos con reason no vacío."""

    def setUp(self):
        self.user = User.objects.create_user(username='prio_user', password='test1234')
        self.event = Event.objects.create(
            name='Evento Prio', owner=self.user, status='active',
            start_date=timezone.now() + timedelta(days=5),
        )

    def test_returns_simplenamespace_objects(self):
        from types import SimpleNamespace
        from modules.models import Task
        from events.engine.prioritizer import prioritize_tasks
        Task.objects.create(event=self.event, title='T1', priority='high', status='pending')
        result = prioritize_tasks(self.event.tasks.filter(status__in=['pending', 'in_progress']))
        self.assertIsInstance(result[0], SimpleNamespace)

    def test_each_item_has_non_empty_reason(self):
        from modules.models import Task
        from events.engine.prioritizer import prioritize_tasks
        Task.objects.create(event=self.event, title='T1', priority='high', status='pending')
        Task.objects.create(event=self.event, title='T2', priority='low', status='in_progress')
        result = prioritize_tasks(self.event.tasks.filter(status__in=['pending', 'in_progress']))
        for item in result:
            self.assertTrue(len(item.reason) > 0)

    def test_high_priority_task_ranked_first(self):
        from modules.models import Task
        from events.engine.prioritizer import prioritize_tasks
        Task.objects.create(event=self.event, title='Low', priority='low', status='pending')
        Task.objects.create(event=self.event, title='High', priority='high', status='pending')
        result = prioritize_tasks(self.event.tasks.filter(status__in=['pending', 'in_progress']))
        self.assertEqual(result[0].task.title, 'High')

    def test_overdue_task_ranked_first(self):
        from modules.models import Task
        from events.engine.prioritizer import prioritize_tasks
        past = timezone.now().date() - timedelta(days=3)
        Task.objects.create(event=self.event, title='Normal', priority='high', status='pending')
        Task.objects.create(event=self.event, title='Vencida', priority='low',
                            status='pending', due_date=past)
        result = prioritize_tasks(self.event.tasks.filter(status__in=['pending', 'in_progress']))
        # La vencida tiene +40 por overdue, suficiente para superar a la high sin fecha
        self.assertEqual(result[0].task.title, 'Vencida')


class EventCompletionTest(TestCase):
    """Al marcar evento como completado, alertas se auto-dismissan y se crea métrica."""

    def setUp(self):
        self.user = User.objects.create_user(username='comp_user', password='test1234', email='c@c.com')
        self.client = Client()
        self.client.login(username='comp_user', password='test1234')
        self.event = Event.objects.create(
            name='Evento Cierre', owner=self.user, status='active',
            start_date=timezone.now() + timedelta(days=3),
        )
        # Crear alertas activas
        EventAlert.objects.create(
            event=self.event,
            alert_type='deadline',
            severity='critical',
            title='Alerta test',
            message='msg',
            alert_key=f'test-key-{self.event.pk}',
        )

    def test_alerts_dismissed_on_completion(self):
        """Todas las alertas activas deben quedar dismissed al completar."""
        from django.urls import reverse
        url = reverse('events:event_edit', kwargs={'pk': self.event.pk})
        self.client.post(url, {
            'name': self.event.name,
            'status': 'completed',
        })
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'completed')
        active_alerts = EventAlert.objects.filter(event=self.event, is_dismissed=False).count()
        self.assertEqual(active_alerts, 0)

    def test_engine_metrics_created_on_completion(self):
        """Se registra EngineMetrics con action_taken='event_completed'."""
        from django.urls import reverse
        url = reverse('events:event_edit', kwargs={'pk': self.event.pk})
        self.client.post(url, {
            'name': self.event.name,
            'status': 'completed',
        })
        metric = EngineMetrics.objects.filter(
            event=self.event,
            action_taken='event_completed',
        ).first()
        self.assertIsNotNone(metric)
        self.assertTrue(metric.user_acted)
        self.assertTrue(metric.issue_resolved)
