"""
MQTT Publisher Service for Smart Energy Manager.
Dispatches validated DeviceCommands over MQTT topic smart-energy/devices/{device_id}/commands.
"""
import json
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.utils import timezone
from apps.automation.models import DeviceCommand, CommandStatusChoices
from apps.devices.mqtt_client import create_mqtt_client, get_commands_topic
from apps.devices.broadcaster import broadcast_device_update

logger = logging.getLogger('apps.devices.mqtt_publisher')

class MqttCommandPublisher:
    """
    Handles publishing queued device commands to ESP32 / IoT nodes via MQTT.
    """

    def __init__(self, client=None):
        self._client = client

    def get_client(self):
        if self._client is None:
            self._client = create_mqtt_client(client_id=f"{getattr(settings, 'MQTT_CLIENT_ID', 'smart_energy_backend')}_pub")
            host = getattr(settings, 'MQTT_BROKER_HOST', 'localhost')
            port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
            keepalive = getattr(settings, 'MQTT_KEEPALIVE', 60)
            self._client.connect(host, port, keepalive)
        return self._client

    def publish_command(self, command: DeviceCommand) -> bool:
        """
        Publishes a single DeviceCommand to smart-energy/devices/{device_id}/commands.
        Updates command status to SENT.
        Does NOT update RelayChannel.is_on until verified ACK is received.
        """
        device = command.device
        channel = command.channel

        # Safety Check: Do not publish if channel is safety locked
        if channel.safety_locked:
            command.status = CommandStatusChoices.FAILED
            command.failure_reason = "Relay channel is safety-locked. Automated dispatch blocked."
            command.save(update_fields=['status', 'failure_reason', 'updated_at'])
            logger.warning("Blocked MQTT dispatch for safety-locked channel %s on %s", channel.channel_index, device.hardware_id)
            return False

        topic = get_commands_topic(device.hardware_id)
        payload = {
            "command_id": str(command.command_id),
            "channel_index": channel.channel_index,
            "target_state": command.target_state,
            "source": command.source,
            "timestamp": timezone.now().isoformat()
        }

        qos = getattr(settings, 'MQTT_QOS', 1)
        try:
            client = self.get_client()
            client.publish(topic, json.dumps(payload), qos=qos)
            command.status = CommandStatusChoices.SENT
            command.save(update_fields=['status', 'updated_at'])

            # Realtime broadcast of command dispatched
            broadcast_device_update(device.hardware_id, {
                "event": "COMMAND_SENT",
                "command_id": str(command.command_id),
                "channel_index": channel.channel_index,
                "target_state": command.target_state
            })

            logger.info("Published command %s to topic %s", command.command_id, topic)
            return True
        except Exception as exc:
            command.status = CommandStatusChoices.FAILED
            command.failure_reason = f"MQTT publish failed: {str(exc)}"
            command.save(update_fields=['status', 'failure_reason', 'updated_at'])
            logger.error("Failed to publish command %s: %s", command.command_id, exc)
            return False

    def close(self):
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

