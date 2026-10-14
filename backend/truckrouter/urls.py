import os
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import FileResponse, HttpResponse
from django.views.static import serve
from django.conf import settings


def index_view(request):
    index_file = settings.BASE_DIR / 'frontend_dist' / 'index.html'
    if os.path.exists(index_file):
        return FileResponse(open(index_file, 'rb'), content_type='text/html')
    return HttpResponse('TruckRouter API is running. Access /api/route/')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('routes.urls')),
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'frontend_dist' / 'assets'}),
    re_path(r'^(?!api|admin|static).*$', index_view),
]
