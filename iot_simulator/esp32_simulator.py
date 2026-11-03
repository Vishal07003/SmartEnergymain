"""
Simulated ESP32 IoT Node for Smart Energy Manager.
Simulates a physical ESP32 device running firmware that:
- Connects to the MQTT broker.
- Authenticates using unique device auth_token.
- Periodically publishes sensor telemetry and heartbeats with explicit SIMULATED markers.
- Subscribes to smart-energy/devices/{device_id}/commands.
- Simulates physical relay ON/OFF actuation.
- Publishes acknowledgment to smart-energy/devices/{device_id}/ack.
- Prevents duplicate command execution.
"""
import time
import json
import logging
import random
from datetime import datetime
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [SIMULATOR] %(levelname)s - %(message)s')
logger = logging.getLogger('ESP32Simulator')

class ESP32DeviceSimulator:
    def __init__(
        self,
        hardware_id: str,
        auth_token: str,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        topic_prefix: str = "smart-energy",
        username: str = "",
        password: str = "",
        use_tls: bool = False
    ):
        self.hardware_id = hardware_id
        self.auth_token = auth_token
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self.username = username
        self.password = password
        self.use_tls = use_tls

        # Internal simulated hardware state
        self.channel_states: Dict[int, bool] = {1: False, 2: False, 3: False, 4: False}
        self.executed_command_ids = set()
        self.uptime_seconds = 0
        self.wifi_rssi = -60

        # MQTT topics
        self.topic_telemetry = f"{topic_prefix}/devices/{hardware_id}/telemetry"
        self.topic_heartbeat = f"{topic_prefix}/devices/{hardware_id}/heartbeat"
        self.topic_commands = f"{topic_prefix}/devices/{hardware_id}/commands"
        self.topic_ack = f"{topic_prefix}/devices/{hardware_id}/ack"

        # Initialize Paho MQTT client
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"sim_{hardware_id}"
            )
        except AttributeError:
            self.client = mqtt.Client(client_id=f"sim_{hardware_id}")

        if username:
            self.client.username_pw_set(username, password)
        if use_tls:
            self.client.tls_set()

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        logger.info("Connected to MQTT broker with result code: %s", rc)
        # Subscribe to incoming commands
        client.subscribe(self.topic_commands, qos=1)
        logger.info("Subscribed to command topic: %s", self.topic_commands)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        logger.warning("Disconnected from MQTT broker (rc: %s). Will attempt reconnect.", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            self.handle_incoming_command(payload)
        except Exception as exc:
            logger.error("Error processing incoming command on %s: %s", msg.topic, exc)

    def handle_incoming_command(self, payload: Dict[str, Any]):
        cmd_id = payload.get('command_id')
        channel_index = payload.get('channel_index')
        target_state = payload.get('target_state')

        if not cmd_id or channel_index is None or target_state is None:
            logger.warning("Received invalid command payload: %s", payload)
            return

        # Check for duplicate execution
        if cmd_id in self.executed_command_ids:
            logger.info("Duplicate command ID %s received. Re-sending ACK.", cmd_id)
            self.send_ack(cmd_id, self.channel_states.get(channel_index, False), notes="Duplicate execution ignored; state re-ACKed")
            return

        # Simulate relay physical actuation
        logger.info("ACTUATING RELAY Ch#%s -> %s (Command ID: %s)", channel_index, "ON" if target_state else "OFF", cmd_id)
        time.sleep(0.1)  # Simulate 100ms hardware switching delay
        self.channel_states[channel_index] = bool(target_state)
        self.executed_command_ids.add(cmd_id)

        # Publish acknowledgment packet
        self.send_ack(cmd_id, self.channel_states[channel_index], notes="Relay switched successfully by ESP32 simulator")

    def send_ack(self, command_id: str, reported_state: bool, notes: str = ""):
        ack_payload = {
            "auth_token": self.auth_token,
            "command_id": command_id,
            "reported_state": reported_state,
            "notes": notes,
            "simulated": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.client.publish(self.topic_ack, json.dumps(ack_payload), qos=1)
        logger.info("Published ACK for command %s on %s (state: %s)", command_id, self.topic_ack, reported_state)

    def publish_telemetry(self, sensor_readings: Optional[list] = None, electrical_data: Optional[dict] = None):
        """
        Publishes telemetry metrics with explicit 'simulated': True marker.
        """
        payload = {
            "auth_token": self.auth_token,
            "simulated": True,
            "timestamp": datetime.utcnow().isoformat(),
            "readings": sensor_readings or [
                {"sensor_type": "TEMPERATURE", "value": round(23.5 + random.uniform(-1.0, 1.0), 2)},
                {"sensor_type": "HUMIDITY", "value": round(55.0 + random.uniform(-3.0, 3.0), 1)},
                {"sensor_type": "LUX", "value": round(420.0 + random.uniform(-20.0, 20.0), 1)}
            ]
        }
        if electrical_data:
            payload.update(electrical_data)
        else:
            payload.update({
                "voltage": round(230.0 + random.uniform(-3.0, 3.0), 1),
                "current": round(2.5 + random.uniform(-0.5, 0.5), 2),
                "active_power_watts": round(550.0 + random.uniform(-50.0, 50.0), 1),
                "power_factor": 0.96,
                "energy_kwh": round(12.4 + self.uptime_seconds * 0.0001, 3)
            })

        self.client.publish(self.topic_telemetry, json.dumps(payload), qos=1)
        logger.info("Published SIMULATED telemetry packet to %s", self.topic_telemetry)

    def publish_heartbeat(self):
        """
        Publishes periodic heartbeat packet.
        """
        self.uptime_seconds += 15
        payload = {
            "auth_token": self.auth_token,
            "simulated": True,
            "voltage": round(230.0 + random.uniform(-2.0, 2.0), 1),
            "current": 2.5,
            "power_watts": 575.0,
            "wifi_rssi": self.wifi_rssi + random.randint(-2, 2),
            "uptime_seconds": self.uptime_seconds,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.client.publish(self.topic_heartbeat, json.dumps(payload), qos=1)
        logger.info("Published SIMULATED heartbeat to %s (uptime: %ss)", self.topic_heartbeat, self.uptime_seconds)

    def start(self):
        logger.info("Connecting to broker %s:%s...", self.broker_host, self.broker_port)
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Simulator stopped.")

