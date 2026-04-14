from django.contrib import admin
from .models import (
    EventTemplate, TemplateModule, Event, EventModule,
    TemplateTask, TemplateChecklistItem, EventAlert, EngineMetrics,
)


@admin.register(EventTemplate)
class EventTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'created_by', 'created_at']
    list_filter = ['category']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'status', 'start_date', 'created_at']
    list_filter = ['status']


admin.site.register(TemplateModule)
admin.site.register(EventModule)


@admin.register(TemplateTask)
class TemplateTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'template', 'priority', 'days_before_event', 'order']
    list_filter = ['priority', 'template']
    ordering = ['template', 'order']


@admin.register(TemplateChecklistItem)
class TemplateChecklistItemAdmin(admin.ModelAdmin):
    list_display = ['checklist_title', 'item_text', 'template', 'order']
    list_filter = ['template']


@admin.register(EventAlert)
class EventAlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'alert_type', 'severity', 'is_read', 'is_dismissed', 'created_at']
    list_filter = ['severity', 'alert_type', 'is_dismissed', 'is_read']
    search_fields = ['title', 'alert_key']


@admin.register(EngineMetrics)
class EngineMetricsAdmin(admin.ModelAdmin):
    list_display = ['decision_key', 'decision_type', 'user_acted', 'action_taken', 'created_at']
    list_filter = ['decision_type', 'user_acted']
    readonly_fields = ['created_at']