import uuid
import threading
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import RouteJob
from .serializers import RouteRequestSerializer, RouteJobSerializer
from .tasks import compute_routes

logger = logging.getLogger(__name__)


class RouteCreateView(APIView):
    """
    POST /api/route/
    Body: { origin, destination, departure_time, load_weight_lbs }
    Returns: { job_id, task_id, status }
    """
    def post(self, request):
        ser = RouteRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        job = RouteJob.objects.create(
            origin=ser.validated_data['origin'],
            destination=ser.validated_data['destination'],
            departure_time=ser.validated_data['departure_time'],
            load_weight_lbs=ser.validated_data['load_weight_lbs'],
        )

        task_id = str(uuid.uuid4())
        import socket
        redis_available = False
        try:
            with socket.create_connection(('localhost', 6379), timeout=0.2):
                redis_available = True
        except Exception:
            pass

        if redis_available:
            try:
                task = compute_routes.delay(job.id)
                task_id = task.id
            except Exception as e:
                logger.info('Celery dispatch failed: %s', e)
                threading.Thread(target=compute_routes, args=(job.id,), daemon=True).start()
        else:
            threading.Thread(target=compute_routes, args=(job.id,), daemon=True).start()

        job.task_id = task_id
        job.save(update_fields=['task_id'])

        return Response(
            {'job_id': job.id, 'task_id': task_id, 'status': job.status},
            status=status.HTTP_202_ACCEPTED,
        )


class RouteStatusView(APIView):
    """
    GET /api/route/<job_id>/
    Returns full job result once status == 'done'.
    """
    def get(self, request, job_id):
        try:
            job = RouteJob.objects.get(id=job_id)
        except RouteJob.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        ser = RouteJobSerializer(job)
        return Response(ser.data)
