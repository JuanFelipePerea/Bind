from django.urls import path
from . import views
from . import views_bynix
from . import views_collaborator

app_name = 'events'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),                    # Panel principal
    path('events/', views.event_list, name='event_list'),           # Lista de proyectos
    path('events/new/', views.event_create, name='event_create'),   # Crear evento
    path('events/<int:pk>/', views.event_detail, name='event_detail'),  # Detalle
    path('events/<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('events/<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('events/<int:pk>/modules/', views.event_modules_manage, name='event_modules_manage'),
    path('en-curso/', views.eventos_en_curso, name='eventos_en_curso'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/new/', views.template_create, name='template_create'),
    path('templates/<int:template_id>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:template_id>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:template_id>/quick-create/', views.quick_create_from_template, name='quick_create_from_template'),
    path('templates/<int:template_id>/preview.json', views.template_preview_json, name='template_preview_json'),
    path('report/', views.report_view, name='report'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('alerts/<int:pk>/dismiss/', views.alert_dismiss, name='alert_dismiss'),
    path('alerts/<int:pk>/action/', views.alert_action, name='alert_action'),
    path('search/', views.global_search, name='search'),
    path('events/<int:pk>/bynix/', views_bynix.event_assistant_chat, name='event_assistant_chat'),
    path('events/<int:pk>/bynix/capture/', views_bynix.bynix_quick_capture, name='bynix_quick_capture'),
    # Momentos
    path('events/<int:event_pk>/momentos/nuevo/',              views.momento_create, name='momento_create'),
    path('events/<int:event_pk>/momentos/<int:pk>/editar/',    views.momento_edit,   name='momento_edit'),
    path('events/<int:event_pk>/momentos/<int:pk>/eliminar/',  views.momento_delete, name='momento_delete'),
    path('events/<int:event_pk>/momentos.json',                views.momentos_json,  name='momentos_json'),
    # Layout persistence
    path('events/<int:pk>/layout/', views.save_layout_config, name='save_layout_config'),
    # Bynix — Dashboard (global, sin evento específico)
    path('bynix/', views_bynix.dashboard_assistant_chat, name='dashboard_assistant_chat'),
    # Events API — creación rápida vía IA
    path('events/api/create/', views.event_api_create, name='event_api_create'),
    # Colaboración
    path('events/<int:pk>/collaborators/', views_collaborator.list_collaborators, name='list_collaborators'),
    path('events/<int:pk>/collaborators/invite/', views_collaborator.invite_collaborator, name='invite_collaborator'),
    path('events/<int:pk>/collaborators/accept/', views_collaborator.accept_invitation, name='accept_invitation'),
]