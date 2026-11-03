"""
MQTT Infrastructure and Client Configuration for Smart Energy Manager.
Provides reusable configuration, connection factory, and topic format definitions.
"""
import ssl
import logging
from typing import Optional, Dict, Any
from django.conf import settings
import paho.mqtt.client as mqtt

logger = logging.getLogger('apps.devices.mqtt')

# MQTT Topic Template Formats
TOPIC_TELEMETRY = "{prefix}/devices/{device_id}/telemetry"
TOPIC_HEARTBEAT = "{prefix}/devices/{device_id}/heartbeat"
TOPIC_COMMANDS = "{prefix}/devices/{device_id}/commands"
TOPIC_ACK = "{prefix}/devices/{device_id}/ack"

def get_topic_prefix() -> str:
    return getattr(settings, 'MQTT_TOPIC_PREFIX', 'smart-energy')

def get_telemetry_topic(hardware_id: str) -> str:
    return TOPIC_TELEMETRY.format(prefix=get_topic_prefix(), device_id=hardware_id)

def get_heartbeat_topic(hardware_id: str) -> str:
    return TOPIC_HEARTBEAT.format(prefix=get_topic_prefix(), device_id=hardware_id)

def get_commands_topic(hardware_id: str) -> str:
    return TOPIC_COMMANDS.format(prefix=get_topic_prefix(), device_id=hardware_id)

def get_ack_topic(hardware_id: str) -> str:
    return TOPIC_ACK.format(prefix=get_topic_prefix(), device_id=hardware_id)

def get_all_telemetry_subscription_topic() -> str:
    return f"{get_topic_prefix()}/devices/+/telemetry"

def get_all_heartbeat_subscription_topic() -> str:
    return f"{get_topic_prefix()}/devices/+/heartbeat"

def get_all_ack_subscription_topic() -> str:
    return f"{get_topic_prefix()}/devices/+/ack"

def create_mqtt_client(client_id: Optional[str] = None, clean_session: bool = True) -> mqtt.Client:
    """
    Creates and configures a Paho MQTT Client instance with institutional settings.
    Supports TLS, username/password auth, and protocol v5 or v3.1.1.
    """
    cid = client_id or getattr(settings, 'MQTT_CLIENT_ID', 'smart_energy_backend')

    # Compatible with paho-mqtt 2.x and 1.x
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=cid,
            clean_session=clean_session
        )
    except AttributeError:
        client = mqtt.Client(
            client_id=cid,
            clean_session=clean_session
        )

    username = getattr(settings, 'MQTT_USERNAME', '')
    password = getattr(settings, 'MQTT_PASSWORD', '')
    if username:
        client.username_pw_set(username=username, password=password)

    if getattr(settings, 'MQTT_USE_TLS', False):
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    return client

