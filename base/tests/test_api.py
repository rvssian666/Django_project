import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from base.models import Message, Room, Topic

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username='ana', password='ClaveSegura123')


@pytest.fixture
def other_user():
    return User.objects.create_user(username='bruno', password='ClaveSegura123')


@pytest.fixture
def auth_client(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


@pytest.fixture
def other_auth_client(other_user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=other_user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


@pytest.fixture
def topic():
    return Topic.objects.create(name='Python')


@pytest.fixture
def room(user, topic):
    return Room.objects.create(
        host=user,
        topic=topic,
        name='Sala de Python',
        description='Aprender Django y DRF',
    )


@pytest.fixture
def message(user, room):
    return Message.objects.create(
        user=user,
        room=room,
        body='Hola, empecemos con los serializers de DRF.',
    )


class TestModels:
    """Creacion de los modelos base del dominio."""

    def test_topic_creation_and_str(self, topic):
        assert topic.pk is not None
        assert str(topic) == 'Python'

    def test_room_creation_assigns_host_and_topic(self, room, user, topic):
        assert room.host == user
        assert room.topic == topic
        assert str(room) == 'Sala de Python'

    def test_message_creation_links_user_and_room(self, message, user, room):
        assert message.user == user
        assert message.room == room
        assert message in room.message_set.all()
        assert str(message) == 'Hola, empecemos con los serializers de DRF.'


class TestAuthEndpoints:
    """Autenticacion por token (TokenAuthentication)."""

    def test_obtain_token_with_valid_credentials(self, api_client, user):
        response = api_client.post(
            '/api/v1/auth/token/',
            {'username': 'ana', 'password': 'ClaveSegura123'},
            format='json',
        )
        assert response.status_code == 200
        assert response.data['token'] == Token.objects.get(user=user).key
        assert response.data['username'] == 'ana'

    def test_obtain_token_with_invalid_credentials(self, api_client, user):
        response = api_client.post(
            '/api/v1/auth/token/',
            {'username': 'ana', 'password': 'incorrecta'},
            format='json',
        )
        assert response.status_code == 400

    def test_token_auth_accesses_me_endpoint(self, auth_client, user):
        response = auth_client.get('/api/v1/users/me/')
        assert response.status_code == 200
        assert response.data['username'] == user.username

    def test_me_endpoint_requires_authentication(self, api_client):
        response = api_client.get('/api/v1/users/me/')
        assert response.status_code == 401


class TestRoomAPI:
    """CRUD de salas con permisos de anfitrion."""

    def test_list_and_detail_rooms_are_public(self, api_client, room):
        listing = api_client.get('/api/v1/rooms/')
        assert listing.status_code == 200
        assert listing.data['count'] == 1
        assert listing.data['results'][0]['name'] == room.name

        detail = api_client.get(f'/api/v1/rooms/{room.id}/')
        assert detail.status_code == 200
        assert detail.data['host']['username'] == room.host.username
        assert detail.data['topic']['name'] == room.topic.name

    def test_create_room_requires_authentication(self, api_client, topic):
        response = api_client.post(
            '/api/v1/rooms/', {'name': 'Sala anonima', 'topic_id': topic.id}, format='json'
        )
        assert response.status_code == 401

    def test_create_room_authenticated_assigns_host(self, auth_client, user, topic):
        response = auth_client.post(
            '/api/v1/rooms/',
            {'name': 'Sala creada por API', 'description': 'Con token', 'topic_id': topic.id},
            format='json',
        )
        assert response.status_code == 201
        created = Room.objects.get(id=response.data['id'])
        assert created.host == user
        assert created.topic == topic

    def test_host_can_update_room(self, auth_client, room):
        response = auth_client.patch(
            f'/api/v1/rooms/{room.id}/', {'name': 'Nombre actualizado'}, format='json'
        )
        assert response.status_code == 200
        room.refresh_from_db()
        assert room.name == 'Nombre actualizado'

    def test_non_host_cannot_update_or_delete_room(self, other_auth_client, room):
        update = other_auth_client.patch(
            f'/api/v1/rooms/{room.id}/', {'name': 'Hackeado'}, format='json'
        )
        assert update.status_code == 403

        delete = other_auth_client.delete(f'/api/v1/rooms/{room.id}/')
        assert delete.status_code == 403

        room.refresh_from_db()
        assert room.name == 'Sala de Python'
        assert Room.objects.filter(id=room.id).exists()

    def test_host_can_delete_room(self, auth_client, room):
        response = auth_client.delete(f'/api/v1/rooms/{room.id}/')
        assert response.status_code == 204
        assert not Room.objects.filter(id=room.id).exists()


class TestTopicAPI:
    """Lectura publica y creacion autenticada de temas."""

    def test_list_topics_is_public(self, api_client, topic):
        response = api_client.get('/api/v1/topics/')
        assert response.status_code == 200
        assert response.data['count'] == 1
        assert response.data['results'][0]['name'] == 'Python'

    def test_create_topic_requires_authentication(self, api_client):
        response = api_client.post('/api/v1/topics/', {'name': 'Django'}, format='json')
        assert response.status_code == 401

    def test_create_topic_authenticated(self, auth_client):
        response = auth_client.post('/api/v1/topics/', {'name': 'Django'}, format='json')
        assert response.status_code == 201
        assert Topic.objects.filter(name='Django').exists()


class TestMessageAPI:
    """Listado/creacion/borrado de mensajes con permisos de autor o anfitrion."""

    def test_list_messages_filtered_by_room(self, api_client, message, user, topic):
        other_room = Room.objects.create(host=user, topic=topic, name='Otra sala')
        Message.objects.create(user=user, room=other_room, body='Mensaje de otra sala')

        response = api_client.get('/api/v1/messages/', {'room': message.room_id})
        assert response.status_code == 200
        assert response.data['count'] == 1
        assert response.data['results'][0]['body'] == message.body

    def test_create_message_requires_authentication(self, api_client, room):
        response = api_client.post(
            '/api/v1/messages/', {'room': room.id, 'body': 'Anonimo'}, format='json'
        )
        assert response.status_code == 401

    def test_create_message_authenticated_assigns_user(self, auth_client, user, room):
        response = auth_client.post(
            '/api/v1/messages/', {'room': room.id, 'body': 'Mensaje via API'}, format='json'
        )
        assert response.status_code == 201
        created = Message.objects.get(id=response.data['id'])
        assert created.user == user
        assert created.room == room

    def test_author_can_delete_message(self, auth_client, message):
        response = auth_client.delete(f'/api/v1/messages/{message.id}/')
        assert response.status_code == 204
        assert not Message.objects.filter(id=message.id).exists()

    def test_non_author_non_host_cannot_delete_message(self, other_auth_client, message):
        response = other_auth_client.delete(f'/api/v1/messages/{message.id}/')
        assert response.status_code == 403
        assert Message.objects.filter(id=message.id).exists()


class TestRoomSummaryAPI:
    """Endpoint diferencial de resumen para webhooks (n8n/Make) y LLMs."""

    def test_summary_requires_authentication(self, api_client, room):
        response = api_client.get(f'/api/v1/rooms/{room.id}/summary/')
        assert response.status_code == 401

    def test_summary_returns_structured_payload(self, auth_client, room, message):
        response = auth_client.get(f'/api/v1/rooms/{room.id}/summary/')
        assert response.status_code == 200
        expected_keys = {'room', 'metrics', 'participants', 'keywords', 'transcript', 'llm_prompt'}
        assert expected_keys.issubset(response.data.keys())
        assert response.data['room']['id'] == room.id
        assert response.data['metrics']['total_messages'] == 1
        assert response.data['metrics']['total_participants'] == 1
        assert response.data['transcript'][0]['author'] == message.user.username
        assert room.name in response.data['llm_prompt']
        assert response.data['ready_for_automation'] is True

    def test_summary_reports_participation_metrics(self, auth_client, room, message, other_user):
        Message.objects.create(user=other_user, room=room, body='Segundo mensaje de la sala')

        response = auth_client.get(f'/api/v1/rooms/{room.id}/summary/')
        assert response.data['metrics']['total_messages'] == 2
        assert response.data['metrics']['total_participants'] == 2
        shares = {p['username']: p['share_percent'] for p in response.data['participants']}
        assert shares[message.user.username] == 50.0
        assert shares[other_user.username] == 50.0
        keywords = {entry['word'] for entry in response.data['keywords']}
        assert 'mensaje' in keywords

    def test_summary_post_accepts_limit_and_instruction(self, auth_client, room, message, other_user):
        for index in range(5):
            Message.objects.create(user=other_user, room=room, body=f'Contenido numero {index}')

        response = auth_client.post(
            f'/api/v1/rooms/{room.id}/summary/',
            {'limit': 3, 'instruction': 'Responde en espanol'},
            format='json',
        )
        assert response.status_code == 200
        assert response.data['metrics']['messages_in_transcript'] == 3
        assert response.data['metrics']['total_messages'] == 6
        assert 'Responde en espanol' in response.data['llm_prompt']

    def test_summary_rejects_invalid_limit(self, auth_client, room):
        response = auth_client.post(
            f'/api/v1/rooms/{room.id}/summary/', {'limit': 0}, format='json'
        )
        assert response.status_code == 400


class TestHTMLViewsStillWork:
    """Las vistas HTML tradicionales siguen funcionando tras anadir la API."""

    def test_home_page_renders(self, api_client, room):
        response = api_client.get('/')
        assert response.status_code == 200
        assert 'text/html' in response['Content-Type']
        assert room.name.encode() in response.content
