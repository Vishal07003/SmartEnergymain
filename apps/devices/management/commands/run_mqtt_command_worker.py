"""
Management command to run the MQTT Command Dispatcher worker.
Polls for queued DeviceCommands, checks device status, applies retries, and publishes to MQTT.
"""
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.automation.models import DeviceCommand, CommandStatusChoices
from apps.devices.mqtt_publisher import MqttCommandPublisher

class Command(BaseCommand):
    help = "Run the MQTT Command Dispatcher worker to publish queued device commands"

    def add_arguments(self, parser):
        parser.add_argument('--poll-interval', type=float, default=2.0, help='Polling interval in seconds')
        parser.add_argument('--timeout-seconds', type=int, default=30, help='Seconds before SENT command expires')

    def handle(self, *args, **options):
        interval = options['poll_interval']
        timeout_seconds = options['timeout_seconds']
        publisher = MqttCommandPublisher()
        self.stdout.write(self.style.SUCCESS(f"Starting MQTT Command Dispatcher worker (interval: {interval}s)..."))

        try:
            while True:
                # 1. Expire stale SENT commands that never received ACK
                stale_cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
                expired_count = DeviceCommand.objects.filter(
                    status=CommandStatusChoices.SENT,
                    updated_at__lte=stale_cutoff
                ).update(
                    status=CommandStatusChoices.EXPIRED,
                    failure_reason=f"Hardware ACK timed out after {timeout_seconds}s"
                )
                if expired_count > 0:
                    self.stdout.write(self.style.WARNING(f"Expired {expired_count} timed-out commands."))

                # 2. Fetch QUEUED commands and publish
                queued_commands = DeviceCommand.objects.filter(
                    status=CommandStatusChoices.QUEUED
                ).select_related('device', 'channel')[:10]

                for cmd in queued_commands:
                    success = publisher.publish_command(cmd)
                    if success:
                        self.stdout.write(self.style.SUCCESS(f"Dispatched command {cmd.command_id} for device {cmd.device.hardware_id}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"Failed dispatching command {cmd.command_id}: {cmd.failure_reason}"))

                time.sleep(interval)
        except KeyboardInterrupt:
            publisher.close()
            self.stdout.write(self.style.WARNING("MQTT Command Dispatcher stopped."))

