from django.contrib import admin
from .models import Task, Attendee, Checklist, ChecklistItem, File, Budget, BudgetItem


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'status', 'priority', 'assigned_to', 'due_date']
    list_filter = ['status', 'priority']


@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'event', 'status']
    list_filter = ['status']


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'created_at']


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ['text', 'checklist', 'is_checked']
    list_filter = ['is_checked']


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'file_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['event', 'total_budget', 'currency', 'created_at']
    list_filter = ['currency']


@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'budget', 'amount', 'item_type', 'category', 'paid']
    list_filter = ['item_type', 'category', 'paid']