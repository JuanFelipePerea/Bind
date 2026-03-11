from django.contrib import admin
from .models import EventTemplate, TemplateModule, Event, EventModule

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