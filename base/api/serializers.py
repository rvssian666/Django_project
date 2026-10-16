from django.contrib.auth.models import User
from rest_framework import serializers

from base.models import Message, Room, Topic


class UserSerializer(serializers.ModelSerializer):
    """Serializa el usuario de Django exponiendo solo campos publicos y utiles."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = fields


class TopicSerializer(serializers.ModelSerializer):
    """Tema/categoria de una sala, con el numero de salas asociadas."""

    room_count = serializers.IntegerField(source='room_set.count', read_only=True)

    class Meta:
        model = Topic
        fields = ['id', 'name', 'room_count']


class MessageSerializer(serializers.ModelSerializer):
    """Mensaje perteneciente a una sala; el autor se resuelve desde la sesion/token."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'user', 'room', 'body', 'updated', 'created']
        read_only_fields = ['updated', 'created']


class RoomSerializer(serializers.ModelSerializer):
    """Sala de estudio con host y topic anidados de solo lectura y `topic_id` de escritura."""

    host = UserSerializer(read_only=True)
    topic = TopicSerializer(read_only=True)
    topic_id = serializers.PrimaryKeyRelatedField(
        queryset=Topic.objects.all(),
        source='topic',
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Room
        fields = ['id', 'host', 'topic', 'topic_id', 'name', 'description', 'updated', 'created']
        read_only_fields = ['updated', 'created']


class RoomSummaryRequestSerializer(serializers.Serializer):
    """Valida los parametros de entrada del endpoint de resumen (GET query params o POST JSON)."""

    limit = serializers.IntegerField(min_value=1, max_value=500, required=False, default=100)
    since = serializers.DateTimeField(required=False, allow_null=True)
    instruction = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=''
    )
