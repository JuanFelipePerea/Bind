from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Google OAuth (allauth) — prefix distinto a /accounts/ para evitar conflictos
    path('auth/', include('allauth.urls')),

    # Alias conveniente que usa LOGIN_REDIRECT_URL
    path('dashboard/', RedirectView.as_view(url='/', permanent=False), name='dashboard_redirect'),

    path('', include('events.urls')),
    path('accounts/', include('accounts.urls')),
    path('modules/', include('modules.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # django-debug-toolbar
    import debug_toolbar
    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]

    # django-silk
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
