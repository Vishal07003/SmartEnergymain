"""
WebSocket URL Routing for Smart Energy Manager real-time updates.
"""
from django.urls import path, re_path
from apps.devices.consumers import (
    DeviceConsumer,
    RoomConsumer,
    EnergyConsumer,
    AlertConsumer,
)

websocket_urlpatterns = [
    path('ws/devices/', DeviceConsumer.as_asgi()),
    path('ws/rooms/', RoomConsumer.as_asgi()),
    re_path(r'^ws/rooms/(?P<room_id>\d+)/$', RoomConsumer.as_asgi()),
    path('ws/energy/', EnergyConsumer.as_asgi()),
    path('ws/alerts/', AlertConsumer.as_asgi()),
]

