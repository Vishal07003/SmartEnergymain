"""
Real-time WebSocket event broadcaster utility.
Sends sanitized events to Django Channels groups (devices, rooms, energy, alerts).
Fails gracefully when Channel layer is not running.
"""
import logging
from typing import Dict, Any
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger('apps.realtime')

def broadcast_device_update(hardware_id: str, data: Dict[str, Any]) -> None:
    """Broadcast device status or relay changes to the 'devices' group."""
    _send_to_group('devices', {
        'type': 'device_event',
        'hardware_id': hardware_id,
        'data': data
    })

def broadcast_room_telemetry(room_id: int, data: Dict[str, Any]) -> None:
    """Broadcast room sensor telemetry updates to 'rooms_{room_id}' and 'rooms' group."""
    _send_to_group('rooms', {
        'type': 'telemetry_event',
        'room_id': room_id,
        'data': data
    })
    _send_to_group(f'room_{room_id}', {
        'type': 'telemetry_event',
        'room_id': room_id,
        'data': data
    })

def broadcast_energy_reading(room_id: int, data: Dict[str, Any]) -> None:
    """Broadcast latest power/energy reading to 'energy' group."""
    _send_to_group('energy', {
        'type': 'energy_event',
        'room_id': room_id,
        'data': data
    })

def broadcast_new_alert(alert_data: Dict[str, Any]) -> None:
    """Broadcast new AI/system alert to 'alerts' group."""
    _send_to_group('alerts', {
        'type': 'alert_event',
        'data': alert_data
    })

def _send_to_group(group_name: str, payload: Dict[str, Any]) -> None:
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(group_name, {
                'type': 'broadcast_message',
                'message': payload
            })
    except Exception as exc:
        logger.warning("Channel layer broadcast to '%s' failed: %s", group_name, exc)

