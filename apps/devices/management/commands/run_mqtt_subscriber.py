"""
Management command to run the background MQTT Telemetry & ACK Subscriber daemon.
"""
from django.core.management.base import BaseCommand
from apps.devices.mqtt_subscriber import MqttSubscriberService

class Command(BaseCommand):
    help = "Run the MQTT subscriber background worker for ESP32 telemetry, heartbeats, and ACKs"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting MQTT Subscriber worker..."))
        subscriber = MqttSubscriberService()
        try:
            subscriber.start_listening()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("MQTT Subscriber worker stopped."))

