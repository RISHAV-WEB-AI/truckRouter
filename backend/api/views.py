from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .serializers import RouteRequestSerializer, RouteOptionSerializer
from routes.models import RouteRequest
from routes.tasks import process_route_request

class RoutePlanView(APIView):
    """Accepts a route planning request and queues a Celery task."""
    def post(self, request, format=None):
        serializer = RouteRequestSerializer(data=request.data)
        if serializer.is_valid():
            route_req = serializer.save()
            # launch async task
            process_route_request.delay(route_req.id)
            return Response({"request_id": route_req.id, "status": "queued"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RouteResultView(APIView):
    """Returns the full result once processing is finished."""
    def get(self, request, pk, format=None):
        route_req = get_object_or_404(RouteRequest, pk=pk)
        # Serialize nested data
        from routes.serializers import RouteOptionSerializer
        options_qs = route_req.options.all()
        options_ser = RouteOptionSerializer(options_qs, many=True)
        data = {
            "id": route_req.id,
            "origin": route_req.origin,
            "destination": route_req.destination,
            "departure_datetime": route_req.departure_datetime,
            "load_weight": route_req.load_weight,
            "created_at": route_req.created_at,
            "options": options_ser.data,
        }
        return Response(data, status=status.HTTP_200_OK)
