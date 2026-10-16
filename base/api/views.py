import re

from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from rest_framework import generics, mixins, permissions, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.response import Response

from base.models import Message, Room, Topic

from .serializers import (
    MessageSerializer,
    RoomSerializer,
    RoomSummaryRequestSerializer,
    TopicSerializer,
    UserSerializer,
)

STOPWORDS = {
    'como', 'para', 'este', 'esta', 'esto', 'muy', 'pero', 'porque', 'cuando',
    'donde', 'tengo', 'hacer', 'quiero', 'sobre', 'entre', 'desde', 'hola',
    'gracias', 'todo', 'todos', 'algo', 'alguien', 'tambien', 'solo',
    'this', 'that', 'with', 'from', 'have', 'will', 'what', 'when', 'your',
    'about', 'there', 'their', 'they', 'into', 'more', 'than', 'then', 'some',
}


class IsHostOrReadOnly(permissions.BasePermission):
    """Solo el anfitrion de la sala puede modificar o eliminar sus datos."""

    message = 'Solo el anfitrion de la sala puede modificar o eliminar este recurso.'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.host == request.user


class IsMessageAuthorOrRoomHost(permissions.BasePermission):
    """Un mensaje solo puede eliminarlo su autor o el anfitrion de la sala."""

    message = 'Solo el autor del mensaje o el anfitrion de la sala pueden eliminarlo.'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user == obj.user or request.user == obj.room.host


def _extract_keywords(bodies, top_n=10):
    """Extrae las palabras mas repetidas de los mensajes (metadata lista para un LLM)."""
    counter = {}
    for body in bodies:
        for word in re.findall(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}', body.lower()):
            if word in STOPWORDS:
                continue
            counter[word] = counter.get(word, 0) + 1
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [{'word': word, 'occurrences': count} for word, count in ranked[:top_n]]


class CustomAuthToken(ObtainAuthToken):
    """POST /api/v1/auth/token/ -> devuelve el token del usuario y sus datos basicos."""

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
        })


class CurrentUserView(generics.RetrieveAPIView):
    """GET /api/v1/users/me/ -> perfil del usuario autenticado."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class TopicViewSet(viewsets.ModelViewSet):
    """CRUD de temas: lectura publica, escritura solo para usuarios autenticados."""

    queryset = Topic.objects.all().order_by('name')
    serializer_class = TopicSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]


class RoomViewSet(viewsets.ModelViewSet):
    """CRUD de salas + endpoint diferencial de resumen para automatizacion/IA."""

    queryset = Room.objects.select_related('host', 'topic').all()
    serializer_class = RoomSerializer

    def get_permissions(self):
        if self.action in ('create', 'summary'):
            return [permissions.IsAuthenticated()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsHostOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != 'list':
            return queryset
        query = self.request.query_params.get('q')
        topic = self.request.query_params.get('topic')
        host = self.request.query_params.get('host')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(topic__name__icontains=query)
            )
        if topic:
            queryset = queryset.filter(topic_id=topic)
        if host:
            queryset = queryset.filter(host__username=host)
        return queryset

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)

    @action(detail=True, methods=['get', 'post'], url_path='summary')
    def summary(self, request, pk=None):
        """Recopila la actividad de la sala en un JSON listo para n8n/Make o un LLM.

        GET acepta query params y POST acepta JSON con los mismos campos:
        `limit` (maximo de mensajes en la transcripcion), `since` (ISO 8601)
        e `instruction` (indicacion extra para el prompt del LLM).
        """
        room = self.get_object()
        payload = request.data if request.method == 'POST' else request.query_params
        params = RoomSummaryRequestSerializer(data=payload)
        params.is_valid(raise_exception=True)
        options = params.validated_data
        limit = options['limit']
        since = options.get('since')
        instruction = options.get('instruction', '')

        messages = (
            Message.objects.filter(room=room)
            .select_related('user')
            .order_by('created', 'id')
        )
        if since:
            messages = messages.filter(created__gte=since)

        total_messages = messages.count()
        participants = list(
            messages.values('user__id', 'user__username')
            .annotate(message_count=Count('id'), last_message_at=Max('created'))
            .order_by('-message_count', 'user__username')
        )
        for participant in participants:
            participant['user_id'] = participant.pop('user__id')
            participant['username'] = participant.pop('user__username')
            participant['share_percent'] = (
                round(participant['message_count'] * 100 / total_messages, 2)
                if total_messages
                else 0.0
            )

        window = messages.aggregate(first_message_at=Min('created'), last_message_at=Max('created'))
        latest = list(messages.order_by('-created', '-id')[:limit])
        latest.reverse()

        transcript = [
            {
                'id': message.id,
                'author': message.user.username,
                'body': message.body,
                'created': message.created.isoformat(),
            }
            for message in latest
        ]

        topic_name = room.topic.name if room.topic else 'Sin tema'
        host_name = room.host.username if room.host else 'Sin anfitrion'
        prompt_lines = [
            f"Analiza la conversacion de la sala de estudio '{room.name}' "
            f"(tema: {topic_name}, anfitrion: {host_name}).",
            f"La sala acumula {total_messages} mensajes de {len(participants)} participantes.",
            'Genera un resumen ejecutivo con: ideas principales, preguntas abiertas, '
            'acuerdos o decisiones tomadas y proximos pasos.',
        ]
        if instruction:
            prompt_lines.append(f'Instruccion adicional: {instruction}')
        prompt_lines.append('')
        prompt_lines.append('Conversacion:')
        for message in latest:
            prompt_lines.append(
                f'- [{message.created.isoformat()}] {message.user.username}: {message.body}'
            )

        return Response({
            'room': RoomSerializer(room, context={'request': request}).data,
            'metrics': {
                'total_messages': total_messages,
                'total_participants': len(participants),
                'messages_in_transcript': len(transcript),
                'first_message_at': window['first_message_at'],
                'last_message_at': window['last_message_at'],
                'window_since': since,
            },
            'participants': participants,
            'keywords': _extract_keywords([message.body for message in latest]),
            'transcript': transcript,
            'llm_prompt': '\n'.join(prompt_lines),
            'generated_at': timezone.now(),
            'ready_for_automation': True,
        })


class MessageViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Listado, creacion, detalle y borrado de mensajes (sin edicion)."""

    queryset = (
        Message.objects.select_related('user', 'room').all().order_by('-created', '-id')
    )
    serializer_class = MessageSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsMessageAuthorOrRoomHost()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = super().get_queryset()
        room = self.request.query_params.get('room')
        if room:
            queryset = queryset.filter(room_id=room)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
