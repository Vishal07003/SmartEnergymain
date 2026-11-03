"""
MQTT Telemetry, Heartbeat, and Command ACK Subscriber Service.
Processes incoming IoT device messages with strict authentication, validation,
and integration with existing TelemetryReading, DeviceHeartbeat, and DeviceCommand acknowledgement.
"""
import json
import logging
from datetime import timedelta
from typing import Dict, Any, Tuple, Optional
from django.utils import timezone
from django.conf import settings
from apps.devices.models import Device, RelayChannel
from apps.sensors.models import Sensor
from apps.telemetry.models import TelemetryReading, DeviceHeartbeat
from apps.energy.models import EnergyReading
from apps.automation.models import DeviceCommand, CommandStatusChoices
from apps.devices.mqtt_client import (
    create_mqtt_client,
    get_topic_prefix,
    get_all_telemetry_subscription_topic,
    get_all_heartbeat_subscription_topic,
    get_all_ack_subscription_topic,
)
from apps.devices.broadcaster import (
    broadcast_device_update,
    broadcast_room_telemetry,
    broadcast_energy_reading,
)

logger = logging.getLogger('apps.devices.mqtt_subscriber')

class MqttSubscriberService:
    """
    Service responsible for parsing, authenticating, and safely ingesting
    MQTT messages from physical/simulated ESP32 nodes.
    """

    def __init__(self, client=None):
        self._client = client
        self.is_running = False

    def parse_topic(self, topic: str) -> Optional[Tuple[str, str]]:
        """
        Parses topic string '{prefix}/devices/{device_id}/{message_type}'.
        Returns (device_id, message_type) or None if malformed.
        """
        parts = topic.strip('/').split('/')
        prefix = get_topic_prefix()
        # Expecting [prefix, 'devices', device_id, message_type]
        if len(parts) == 4 and parts[0] == prefix and parts[1] == 'devices':
            return parts[2], parts[3]
        return None

    def authenticate_device(self, hardware_id: str, payload: Dict[str, Any]) -> Tuple[bool, Optional[Device], str]:
        """
        Authenticates incoming device message using device token or signature.
        Rejects unknown devices and invalid credentials.
        """
        try:
            device = Device.objects.get(hardware_id=hardware_id)
        except Device.DoesNotExist:
            return False, None, f"Device with hardware_id '{hardware_id}' is not registered."

        auth_token = payload.get('auth_token')
        # If device has an auth_token_hash configured, authentication token is required
        if device.auth_token_hash:
            if not auth_token:
                return False, device, f"Device '{hardware_id}' requires authentication token, but none was provided."
            if not device.verify_auth_token(auth_token):
                return False, device, f"Invalid authentication token for device '{hardware_id}'."

        return True, device, "Authentication successful."

    def process_message(self, topic: str, raw_payload: str) -> Dict[str, Any]:
        """
        Core entry point for processing an individual MQTT message.
        Safe against bad JSON, missing keys, and unexpected exceptions.
        """
        parsed_topic = self.parse_topic(topic)
        if not parsed_topic:
            logger.warning("Rejected MQTT message on invalid topic structure: %s", topic)
            return {"status": "REJECTED", "reason": "Invalid topic structure"}

        hardware_id, msg_type = parsed_topic

        # Parse JSON
        try:
            payload = json.loads(raw_payload)
            if not isinstance(payload, dict):
                return {"status": "REJECTED", "reason": "Payload must be a JSON object"}
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed JSON received on topic %s: %s", topic, exc)
            return {"status": "REJECTED", "reason": f"Invalid JSON: {str(exc)}"}

        # Authenticate Device
        is_auth, device, reason = self.authenticate_device(hardware_id, payload)
        if not is_auth or device is None:
            logger.warning("Authentication failure on topic %s: %s", topic, reason)
            return {"status": "UNAUTHORIZED", "reason": reason}

        # Route by message type
        if msg_type == 'telemetry':
            return self.handle_telemetry(device, payload)
        elif msg_type == 'heartbeat':
            return self.handle_heartbeat(device, payload)
        elif msg_type == 'ack':
            return self.handle_ack(device, payload)
        else:
            return {"status": "REJECTED", "reason": f"Unknown message type '{msg_type}'"}


    def handle_telemetry(self, device: Device, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes sensor telemetry readings.
        Payload can contain 'readings': list of sensor measurements,
        or electrical metrics ('voltage', 'current', 'active_power_watts', etc.).
        """
        readings = payload.get('readings', [])
        recorded_count = 0

        # Process standard sensor readings list: [{'sensor_id': 1, 'sensor_type': 'TEMPERATURE', 'value': 24.5}]
        for item in readings:
            sensor_id = item.get('sensor_id')
            sensor_type = item.get('sensor_type')
            value = item.get('value')

            if value is None:
                continue

            # Lookup sensor assigned to this device
            sensor_qs = Sensor.objects.filter(device=device, is_active=True)
            if sensor_id:
                sensor = sensor_qs.filter(id=sensor_id).first()
            elif sensor_type:
                sensor = sensor_qs.filter(sensor_type=sensor_type).first()
            else:
                sensor = None

            if not sensor:
                logger.warning("Unmapped sensor in telemetry for device %s: %s", device.hardware_id, item)
                continue

            reading = TelemetryReading.objects.create(
                sensor=sensor,
                value=float(value),
                raw_payload={"source": "mqtt", "simulated": payload.get('simulated', False)}
            )
            recorded_count += 1

            # Broadcast to WebSocket
            broadcast_room_telemetry(sensor.room_id, {
                "sensor_id": sensor.id,
                "sensor_type": sensor.sensor_type,
                "value": reading.value,
                "timestamp": reading.timestamp.isoformat(),
                "simulated": payload.get('simulated', False)
            })

        # Process electrical / energy data if present
        if 'active_power_watts' in payload or 'voltage' in payload:
            voltage = float(payload.get('voltage', 230.0))
            current = float(payload.get('current', 0.0))
            active_power = float(payload.get('active_power_watts', voltage * current))
            energy_kwh = float(payload.get('energy_kwh', 0.0))
            power_factor = float(payload.get('power_factor', 0.95))
            frequency_hz = float(payload.get('frequency_hz', 50.0))

            energy_reading = EnergyReading.objects.create(
                room=device.room,
                device=device,
                voltage_volts=voltage,
                current_amps=current,
                active_power_watts=active_power,
                power_factor=power_factor,
                frequency_hz=frequency_hz,
                energy_kwh=energy_kwh
            )

            broadcast_energy_reading(device.room_id, {
                "reading_id": energy_reading.id,
                "device_hardware_id": device.hardware_id,
                "room_id": device.room_id,
                "voltage": voltage,
                "current": current,
                "active_power_watts": active_power,
                "energy_kwh": energy_kwh,
                "timestamp": energy_reading.timestamp.isoformat(),
                "simulated": payload.get('simulated', False)
            })

        return {"status": "SUCCESS", "readings_recorded": recorded_count}

    def handle_heartbeat(self, device: Device, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes periodic heartbeat transmission from device.
        Applies debounce window of 10s against bursts.
        """
        voltage = float(payload.get('voltage', 230.0))
        current = float(payload.get('current', 0.0))
        power_watts = float(payload.get('power_watts', voltage * current))
        wifi_rssi = int(payload.get('wifi_rssi', -65))
        uptime_seconds = int(payload.get('uptime_seconds', 0))

        # Debounce check
        ten_seconds_ago = timezone.now() - timedelta(seconds=10)
        recent = DeviceHeartbeat.objects.filter(device=device, timestamp__gte=ten_seconds_ago).first()
        if recent:
            return {"status": "SUPPRESSED_BURST_DUPLICATE", "device": device.hardware_id}

        heartbeat = DeviceHeartbeat.objects.create(
            device=device,
            voltage=voltage,
            current=current,
            power_watts=power_watts,
            wifi_rssi=wifi_rssi,
            uptime_seconds=uptime_seconds
        )

        Device.objects.filter(pk=device.pk).update(
            wifi_rssi=wifi_rssi,
            uptime_hours=uptime_seconds // 3600,
            last_communication_time=timezone.now()
        )

        broadcast_device_update(str(device.hardware_id), {
            "event": "HEARTBEAT",
            "heartbeat_id": heartbeat.id,
            "status": "ONLINE",
            "wifi_rssi": wifi_rssi,
            "uptime_hours": uptime_seconds // 3600,
            "timestamp": heartbeat.timestamp.isoformat(),
            "simulated": payload.get('simulated', False)
        })

        return {"status": "SUCCESS", "heartbeat_id": heartbeat.id}

    def handle_ack(self, device: Device, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes command acknowledgment packet from device.
        Updates DeviceCommand status to ACKNOWLEDGED and only now updates RelayChannel.is_on.
        Guards against duplicate ACKs and safety locks.
        """
        command_id = payload.get('command_id')
        reported_state = payload.get('reported_state')

        if not command_id or reported_state is None:
            return {"status": "REJECTED", "reason": "Missing command_id or reported_state in ACK"}

        try:
            command = DeviceCommand.objects.select_related('channel', 'device').get(
                command_id=command_id,
                device=device
            )
        except DeviceCommand.DoesNotExist:
            logger.warning("ACK received for nonexistent command %s on device %s", command_id, device.hardware_id)
            return {"status": "NOT_FOUND", "reason": f"Command '{command_id}' not found for device."}

        # Check for duplicate ACK
        if command.status == CommandStatusChoices.ACKNOWLEDGED:
            return {"status": "DUPLICATE_ACK", "message": "Command already acknowledged"}

        # Safety-locked check
        channel = command.channel
        if channel.safety_locked:
            command.status = CommandStatusChoices.FAILED
            command.failure_reason = "Safety locked during execution acknowledgment."
            command.save(update_fields=['status', 'failure_reason', 'updated_at'])
            return {"status": "BLOCKED_SAFETY_LOCK", "reason": "Relay channel is safety-locked"}

        # Transition command state
        command.status = CommandStatusChoices.ACKNOWLEDGED
        command.hardware_ack_at = timezone.now()
        command.payload['hardware_ack_notes'] = payload.get('notes', 'Simulated/hardware ACK received via MQTT')
        command.save(update_fields=['status', 'hardware_ack_at', 'payload', 'updated_at'])

        # Now and only now update the physical relay channel is_on state
        channel.is_on = bool(reported_state)
        channel.save(update_fields=['is_on', 'updated_at'])

        # Real-time WebSocket broadcast of confirmed state change
        broadcast_device_update(str(device.hardware_id), {
            "event": "RELAY_STATE_CONFIRMED",
            "command_id": str(command.command_id),
            "channel_index": channel.channel_index,
            "is_on": channel.is_on,
            "timestamp": timezone.now().isoformat()
        })

        logger.info("ACK confirmed for command %s on device %s, channel %s is_on=%s",
                    command_id, device.hardware_id, channel.channel_index, channel.is_on)
        return {
            "status": "SUCCESS",
            "command_id": str(command.command_id),
            "reported_state": channel.is_on
        }

    def start_listening(self):
        """Connects to MQTT broker and starts the subscription loop."""
        self._client = create_mqtt_client(client_id=f"{getattr(settings, 'MQTT_CLIENT_ID', 'smart_energy_backend')}_sub")

        def on_connect(client, userdata, flags, rc, properties=None):
            logger.info("MQTT Subscriber connected with result code %s", rc)
            qos = getattr(settings, 'MQTT_QOS', 1)
            client.subscribe(get_all_telemetry_subscription_topic(), qos=qos)
            client.subscribe(get_all_heartbeat_subscription_topic(), qos=qos)
            client.subscribe(get_all_ack_subscription_topic(), qos=qos)
            logger.info("Subscribed to telemetry, heartbeat, and ack topics.")

        def on_message(client, userdata, msg):
            try:
                topic = msg.topic
                raw_payload = msg.payload.decode('utf-8')
                self.process_message(topic, raw_payload)
            except Exception as exc:
                logger.error("Error processing message on %s: %s", msg.topic, exc)

        self._client.on_connect = on_connect
        self._client.on_message = on_message

        host = getattr(settings, 'MQTT_BROKER_HOST', 'localhost')
        port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
        keepalive = getattr(settings, 'MQTT_KEEPALIVE', 60)
        self._client.connect(host, port, keepalive)
        self.is_running = True
        self._client.loop_forever()
