from django.urls import path
from . import views

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
    path('templates/', views.template_list, name='template_list'),  # Plantillas
    path('report/', views.report_view, name='report'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('alerts/<int:pk>/dismiss/', views.alert_dismiss, name='alert_dismiss'),
    path('alerts/<int:pk>/action/', views.alert_action, name='alert_action'),
    path('search/', views.global_search, name='search'),
]