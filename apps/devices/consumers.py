"""
WebSocket Consumers for real-time telemetry, device updates, energy readings, and alerts.
Enforces authentication and staff/admin boundaries.
Never broadcasts credentials or sensitive tokens.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger('apps.devices.consumers')

class BaseAuthenticatedConsumer(AsyncWebsocketConsumer):
    group_name = ""

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            # Reject unauthenticated connections immediately
            await self.close(code=4001)
            return

        # Restrict real-time campus data to active staff/admin
        if not (user.is_staff or getattr(user, 'role', '') in ['ADMIN', 'STAFF']):
            await self.close(code=4003)
            return

        if self.group_name:
            await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def broadcast_message(self, event):
        message = event.get('message', {})
        await self.send(text_data=json.dumps(message))


class DeviceConsumer(BaseAuthenticatedConsumer):
    group_name = "devices"


class RoomConsumer(BaseAuthenticatedConsumer):
    group_name = "rooms"

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        if not (user.is_staff or getattr(user, 'role', '') in ['ADMIN', 'STAFF']):
            await self.close(code=4003)
            return

        # Optional room-specific subscription via URL kwargs
        room_id = self.scope.get('url_route', {}).get('kwargs', {}).get('room_id')
        if room_id:
            self.group_name = f"room_{room_id}"
        else:
            self.group_name = "rooms"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()


class EnergyConsumer(BaseAuthenticatedConsumer):
    group_name = "energy"


class AlertConsumer(BaseAuthenticatedConsumer):
    group_name = "alerts"

