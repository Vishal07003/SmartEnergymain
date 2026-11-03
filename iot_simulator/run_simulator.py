"""
CLI Runner for Simulated ESP32 IoT Node.
Usage:
    python -m iot_simulator.run_simulator --hardware-id ESP32_CS_101 --auth-token <SECRET>
"""
import argparse
import time
import os
from iot_simulator.esp32_simulator import ESP32DeviceSimulator

def main():
    parser = argparse.ArgumentParser(description="Simulated ESP32 IoT Node for Smart Energy Manager")
    parser.add_argument("--hardware-id", default=os.getenv("SIM_HARDWARE_ID", "ESP32_CS_101"), help="Device hardware ID")
    parser.add_argument("--auth-token", default=os.getenv("SIM_AUTH_TOKEN", ""), help="Device authentication secret token")
    parser.add_argument("--host", default=os.getenv("MQTT_BROKER_HOST", "localhost"), help="MQTT broker host")
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", 1883)), help="MQTT broker port")
    parser.add_argument("--interval", type=int, default=10, help="Telemetry publishing interval in seconds")

    args = parser.parse_args()

    simulator = ESP32DeviceSimulator(
        hardware_id=args.hardware_id,
        auth_token=args.auth_token,
        broker_host=args.host,
        broker_port=args.port,
    )

    print(f"=== Starting Simulated ESP32 Node [{args.hardware_id}] ===")
    print(f"Target Broker: {args.host}:{args.port}")
    print("Press Ctrl+C to stop.")

    simulator.start()

    try:
        iteration = 0
        while True:
            time.sleep(args.interval)
            iteration += 1
            # Every interval publish telemetry
            simulator.publish_telemetry()
            # Every 2 intervals publish heartbeat
            if iteration % 2 == 0:
                simulator.publish_heartbeat()
    except KeyboardInterrupt:
        print("\nStopping simulated device...")
        simulator.stop()

if __name__ == "__main__":
    main()

