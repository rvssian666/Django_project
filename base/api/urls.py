from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CurrentUserView,
    CustomAuthToken,
    MessageViewSet,
    RoomViewSet,
    TopicViewSet,
)

app_name = 'api'

router = DefaultRouter()
router.register('rooms', RoomViewSet, basename='room')
router.register('topics', TopicViewSet, basename='topic')
router.register('messages', MessageViewSet, basename='message')

urlpatterns = [
    path('auth/token/', CustomAuthToken.as_view(), name='token'),
    path('users/me/', CurrentUserView.as_view(), name='user-me'),
    path('', include(router.urls)),
]
