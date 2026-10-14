from django.urls import path
from .views import RouteCreateView, RouteStatusView

urlpatterns = [
    path('route/', RouteCreateView.as_view(), name='route-create'),
    path('route/<int:job_id>/', RouteStatusView.as_view(), name='route-status'),
]
