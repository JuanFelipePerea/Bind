from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),                    # Panel principal
    path('events/', views.event_list, name='event_list'),           # Lista de eventos
    path('events/new/', views.event_create, name='event_create'),   # Crear evento
    path('events/<int:pk>/', views.event_detail, name='event_detail'),  # Detalle
    path('events/<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('events/<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('templates/', views.template_list, name='template_list'),  # Plantillas
    path('report/', views.report_view, name='report'),
]