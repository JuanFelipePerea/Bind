from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from events.models import Event
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
        event = Event.objects.create(
            name='Safe Event',
            owner=self.user,
            status='active',
            start_date=timezone.now() + timedelta(days=30),
        )
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
