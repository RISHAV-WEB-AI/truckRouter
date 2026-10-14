from rest_framework import serializers
from .models import RouteJob


class RouteRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=255)
    destination = serializers.CharField(max_length=255)
    departure_time = serializers.DateTimeField()
    load_weight_lbs = serializers.FloatField(min_value=0)


class RouteJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteJob
        fields = ['id', 'task_id', 'origin', 'destination', 'departure_time',
                  'load_weight_lbs', 'status', 'result', 'created_at']
