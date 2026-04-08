from django.urls import path
from . import views

app_name = 'modules'

urlpatterns = [
    # Global tasks overview
    path('tasks/', views.task_overview, name='task_overview'),
    # Tareas
    path('events/<int:event_pk>/tasks/', views.task_list, name='task_list'),
    path('events/<int:event_pk>/tasks/new/', views.task_create, name='task_create'),
    path('events/<int:event_pk>/tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('events/<int:event_pk>/tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),

    # Asistentes
    path('events/<int:event_pk>/attendees/', views.attendee_list, name='attendee_list'),
    path('events/<int:event_pk>/attendees/new/', views.attendee_create, name='attendee_create'),
    path('events/<int:event_pk>/attendees/<int:pk>/edit/', views.attendee_edit, name='attendee_edit'),
    path('events/<int:event_pk>/attendees/<int:pk>/delete/', views.attendee_delete, name='attendee_delete'),

    # Checklists
    path('events/<int:event_pk>/checklists/', views.checklist_list, name='checklist_list'),
    path('events/<int:event_pk>/checklists/new/', views.checklist_create, name='checklist_create'),
    path('checklists/<int:pk>/items/new/', views.checklist_item_create, name='checklist_item_create'),
    path('checklist-items/<int:pk>/toggle/', views.checklist_item_toggle, name='checklist_item_toggle'),
    path('checklists/<int:pk>/delete/', views.checklist_delete, name='checklist_delete'),

    # Archivos
    path('events/<int:event_pk>/files/', views.file_list, name='file_list'),
    path('events/<int:event_pk>/files/new/', views.file_create, name='file_create'),
    path('events/<int:event_pk>/files/<int:pk>/delete/', views.file_delete, name='file_delete'),
    # Task quick actions
    path('tasks/<int:pk>/toggle-done/', views.task_toggle_done, name='task_toggle_done'),
    path('export/tasks/csv/', views.export_tasks_csv, name='export_tasks_csv'),
]