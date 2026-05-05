from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),
    path('register/', views.register_view, name='register'),

    path('profile/',         views.profile_view,      name='profile'),
    path('profile/edit/',    views.profile_edit_view, name='profile_edit'),
    path('2fa/enable/',       views.enable_2fa_send,      name='2fa_enable'),
    path('2fa/verify/',       views.verify_2fa_view,      name='2fa_verify'),
    path('2fa/disable/',      views.disable_2fa_view,     name='2fa_disable'),
    path('login/2fa/',        views.login_2fa_verify_view, name='2fa_login_verify'),

    path('users/',             views.user_list_view,   name='user_list'),
    path('users/<int:pk>/edit/',   views.user_edit_view,   name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete_view, name='user_delete'),
]