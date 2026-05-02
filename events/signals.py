from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from events.engine import invalidate_engine_cache


@receiver(post_save, sender='events.Event')
@receiver(post_delete, sender='events.Event')
def _invalidate_on_event_change(sender, instance, **kwargs):
    invalidate_engine_cache(instance.owner_id)


@receiver(post_save, sender='modules.Task')
def _invalidate_on_task_change(sender, instance, **kwargs):
    # owner_id accede al Event ya cargado en memoria si viene del mismo request;
    # en el peor caso hace 1 query adicional para obtener el FK.
    invalidate_engine_cache(instance.event.owner_id)
