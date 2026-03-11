from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),
    path('register/', views.register_view, name='register'),

    path('profile/',  views.profile_view,  name='profile'),

    path('users/',             views.user_list_view,   name='user_list'),
    path('users/<int:pk>/edit/',   views.user_edit_view,   name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete_view, name='user_delete'),
]