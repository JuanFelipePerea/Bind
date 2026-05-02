from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = 'events'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import events.signals  # noqa: F401 — registra señales de invalidación de caché
