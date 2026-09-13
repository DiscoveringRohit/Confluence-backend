from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/issues/', include('apps.issues.urls')),
    path('api/pitches/', include('apps.pitches.urls')),
    path('api/engagements/', include('apps.engagements.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
