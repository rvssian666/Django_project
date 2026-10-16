# StudyBud API — Plataforma de comunidades de estudio con capa de automatización

Aplicación web de salas de estudio colaborativas (Django + StudyBud) a la que se le ha añadido una **API REST completa** con un endpoint diferencial de **resumen de actividad listo para IA y automatizaciones** (n8n, Make, Zapier o un LLM). El objetivo de negocio es doble: por un lado digitaliza la gestión de comunidades de aprendizaje; por otro, expone los datos de actividad como un servicio consumible por flujos de trabajo automatizados, de modo que cualquier equipo pueda generar resúmenes ejecutivos de sus salas sin intervención manual.

## Impacto en automatización

- **Webhook-ready:** `GET/POST /api/v1/rooms/{id}/summary/` devuelve un JSON estructurado con métricas de participación, transcripción, palabras clave y un `llm_prompt` listo para enviar a un modelo de lenguaje desde n8n/Make.
- **Integración sin fricción:** autenticación por token (`TokenAuthentication`) pensada para clientes máquina-a-máquina, más `SessionAuthentication` para el navegador.
- **Gobernanza de datos:** permisos a nivel de objeto — solo el anfitrión modifica o borra su sala y solo el autor (o el anfitrión) elimina un mensaje.
- **Despliegue reproducible:** Docker + docker-compose con migraciones automáticas.

## Stack tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.14 |
| Framework web | Django | 6.0.1 |
| API REST | Django REST Framework | 3.18.3 |
| Autenticación | DRF TokenAuthentication / SessionAuthentication | — |
| Base de datos | SQLite (desarrollo, incluida) | — |
| Testing | pytest + pytest-django | 9.1.1 / 4.14.0 |
| Contenedores | Docker + docker-compose | — |

## Arquitectura

```
studybud/
├── base/                       # App de dominio (Room, Topic, Message)
│   ├── api/                    # Capa de API REST desacoplada
│   │   ├── serializers.py      # Room, Topic, Message, User + validación de summary
│   │   ├── views.py            # ViewSets, permisos de objeto y endpoint de resumen
│   │   └── urls.py             # Router DRF montado bajo /api/v1/
│   ├── templates/              # Vistas HTML tradicionales (intactas)
│   ├── tests/                  # Suite pytest (27 pruebas)
│   ├── models.py               # Room, Topic, Message
│   └── views.py                # Vistas HTML (home, room, CRUD formularios)
├── studybud/                   # Configuración del proyecto (settings, urls)
├── templates/                  # Plantillas globales (main, navbar)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pytest.ini
```

La API vive en un subpaquete (`base/api/`) y se monta bajo `api/v1/` sin tocar las vistas HTML existentes, que siguen funcionando en la raíz (`/`, `/room/<id>/`, etc.).

## API REST — endpoints principales

| Método | Endpoint | Descripción | Permisos |
|---|---|---|---|
| POST | `/api/v1/auth/token/` | Obtener token de autenticación (usuario/contraseña) | Público |
| GET | `/api/v1/users/me/` | Perfil del usuario autenticado | Token |
| GET | `/api/v1/rooms/` | Listar salas (filtros `?q=`, `?topic=`, `?host=`) | Público |
| POST | `/api/v1/rooms/` | Crear sala (el host se asigna automáticamente) | Token |
| GET | `/api/v1/rooms/{id}/` | Detalle de sala con host y tema anidados | Público |
| PUT / PATCH | `/api/v1/rooms/{id}/` | Actualizar sala | Solo host |
| DELETE | `/api/v1/rooms/{id}/` | Eliminar sala | Solo host |
| GET | `/api/v1/rooms/{id}/summary/` | Resumen de actividad para IA/webhooks | Token |
| POST | `/api/v1/rooms/{id}/summary/` | Resumen con parámetros (`limit`, `since`, `instruction`) | Token |
| GET | `/api/v1/topics/` | Listar temas con número de salas | Público |
| POST | `/api/v1/topics/` | Crear tema | Token |
| GET / PUT / PATCH / DELETE | `/api/v1/topics/{id}/` | Detalle, actualización y borrado de tema | Público / Token |
| GET | `/api/v1/messages/` | Listar mensajes (filtro `?room=<id>`) | Público |
| POST | `/api/v1/messages/` | Publicar mensaje (autor asignado automáticamente) | Token |
| GET | `/api/v1/messages/{id}/` | Detalle de mensaje | Público |
| DELETE | `/api/v1/messages/{id}/` | Eliminar mensaje | Autor o host de la sala |

Los listados están paginados (20 elementos por página) y aceptan `?page=`.

### Ejemplo: token y resumen listo para un LLM

```bash
# 1. Obtener token
curl -X POST http://localhost:8000/api/v1/auth/token/ \
     -H "Content-Type: application/json" \
     -d '{"username": "ana", "password": "ClaveSegura123"}'

# 2. Consumir el resumen de actividad (listo para n8n/Make/LLM)
curl http://localhost:8000/api/v1/rooms/1/summary/?limit=50 \
     -H "Authorization: Token <TU_TOKEN>"
```

Respuesta (estructura):

```json
{
  "room": { "id": 1, "name": "Sala de Python", "host": { "username": "ana" }, "topic": { "name": "Python" } },
  "metrics": {
    "total_messages": 42,
    "total_participants": 5,
    "messages_in_transcript": 50,
    "first_message_at": "2026-10-01T09:00:00Z",
    "last_message_at": "2026-10-16T18:30:00Z"
  },
  "participants": [
    { "user_id": 1, "username": "ana", "message_count": 30, "share_percent": 71.43, "last_message_at": "..." }
  ],
  "keywords": [ { "word": "serializers", "occurrences": 12 } ],
  "transcript": [ { "id": 10, "author": "ana", "body": "...", "created": "..." } ],
  "llm_prompt": "Analiza la conversacion de la sala ...",
  "generated_at": "2026-10-16T19:00:00Z",
  "ready_for_automation": true
}
```

## Puesta en marcha con Docker

```bash
# Construir la imagen
docker compose build

# Levantar el servicio (ejecuta `migrate` automáticamente) en http://localhost:8000
docker compose up -d

# Ver logs
docker compose logs -f web

# Detener y eliminar contenedores
docker compose down
```

## Puesta en marcha local (sin Docker)

Requiere Python 3.12 o superior (el proyecto se desarrolla con Python 3.14 y Django 6).

```bash
# Crear y activar el entorno virtual
python -m venv env
env\Scripts\activate          # Windows
# source env/bin/activate     # Linux / macOS

# Instalar dependencias exactas
pip install -r requirements.txt

# Aplicar migraciones y arrancar
python manage.py migrate
python manage.py runserver
```

## Suite de pruebas (pytest)

27 pruebas unitarias y de integración: creación de modelos, autenticación por token, códigos `200/201/204`, bloqueo `401/403` en rutas protegidas, endpoint de resumen y regresión de las vistas HTML.

```bash
# Ejecutar toda la suite (configurada en pytest.ini)
python -m pytest

# Modo resumido y detallado
python -m pytest -q
python -m pytest base/tests/test_api.py -v

# Ejecutar solo un grupo de pruebas
python -m pytest base/tests/test_api.py::TestRoomSummaryAPI -v
```

## Seguridad

- Lectura pública de salas, temas y mensajes; toda escritura exige autenticación.
- Permisos a nivel de objeto: `IsHostOrReadOnly` (salas) y `IsMessageAuthorOrRoomHost` (mensajes).
- Configuración por variables de entorno: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`.
- `TokenAuthentication` devuelve `401 Unauthorized` a clientes máquina-a-máquina no autenticados.

## Roadmap

- Sustituir SQLite por PostgreSQL en producción.
- Integrar el `llm_prompt` con un webhook real de n8n y un modelo de lenguaje.
- Añadir OpenAPI/Swagger (`drf-spectacular`) y CI con GitHub Actions.
