# Smart Energy Manager – Django Backend

AI-Powered Smart Energy Monitoring and Automation System for Educational Institutions.

## Technology Stack
- **Framework:** Python 3.10+ / Django 5.2 / Django REST Framework
- **Database:** PostgreSQL 18 with `psycopg` (v3)
- **Authentication:** JWT via `djangorestframework-simplejwt`
- **Real-Time / WebSockets:** Django Channels + Daphne ASGI server (Redis-ready)
- **CORS:** `django-cors-headers` for React Native mobile client

---

## Modular Architecture

```text
backend/
├── config/                  # Core Django & Channels configuration
│   ├── settings.py          # Environment-driven settings (decouple)
│   ├── urls.py              # Root routing with /api/v1/ prefix
│   ├── asgi.py              # ProtocolTypeRouter for HTTP & WebSockets
│   └── wsgi.py              # WSGI entry point
├── apps/                    # Modular domain apps
│   ├── accounts/            # Users, auth tokens, RBAC
│   ├── staff/               # Staff profile & assigned buildings
│   ├── rooms/               # Classrooms, labs, occupancy states
│   ├── devices/             # ESP32 nodes, relays, sub-meters
│   ├── sensors/             # PIR, Lux, Sound, Temp, CT sensors
│   ├── telemetry/           # Real-time sensor readings & streams
│   ├── energy/              # Power (W) and consumption (kWh)
│   ├── alerts/              # AI-detected anomalies & wastage
│   ├── analytics/           # Historical & periodic aggregation
│   └── automation/          # Policy engine, schedules & relay rules
├── ai_engine/               # Multi-sensor fusion & ML models
├── tests/                   # Pytest suite
├── requirements.txt         # Project dependencies
├── .env.example             # Template environment variables
├── .env                     # Local environment settings
└── manage.py                # Django CLI management script
```

---

## Database Configuration (PostgreSQL 18)

The backend connects to PostgreSQL via environment variables in `.env`:

```env
DB_NAME=smart_energy_db
DB_USER=smart_energy_user
DB_PASSWORD=smart_energy_secure_password_2026
DB_HOST=127.0.0.1
DB_PORT=5432
```

### Manual PostgreSQL Database & User Setup (If not already created)
Run the following commands in `psql` (as `postgres` superuser):

```sql
CREATE DATABASE smart_energy_db;
CREATE USER smart_energy_user WITH PASSWORD 'smart_energy_secure_password_2026';
GRANT ALL PRIVILEGES ON DATABASE smart_energy_db TO smart_energy_user;
ALTER DATABASE smart_energy_db OWNER TO smart_energy_user;
```

---

## Development Commands

1. **Activate Virtual Environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Run Django System Check:**
   ```powershell
   python manage.py check
   ```

3. **Apply Database Migrations:**
   ```powershell
   python manage.py migrate
   ```

4. **Start ASGI Server (HTTP & WebSockets):**
   ```powershell
   python manage.py runserver
   ```

---

## Phase 10A: IoT MQTT Integration & Real-Time WebSockets

### 1. MQTT Topic Architecture

The system uses standard hierarchical topics configurable by prefix (`smart-energy` by default):

| Purpose | Topic Format | Publisher | Subscriber | QoS |
|---|---|---|---|---|
| **Telemetry** | `smart-energy/devices/{device_id}/telemetry` | ESP32 / Simulator | Backend Subscriber | 1 |
| **Heartbeat** | `smart-energy/devices/{device_id}/heartbeat` | ESP32 / Simulator | Backend Subscriber | 1 |
| **Commands** | `smart-energy/devices/{device_id}/commands` | Backend Dispatcher | ESP32 / Simulator | 1 |
| **Acknowledgment** | `smart-energy/devices/{device_id}/ack` | ESP32 / Simulator | Backend Subscriber | 1 |

### 2. Device Authentication

Every hardware node is authenticated individually using secure hashed tokens:
- Stored as hashed values (`auth_token_hash`) via Django's PBKDF2/cryptographic hashers.
- Tokens can be rotated (`POST /api/v1/devices/{id}/rotate-token/`) or revoked (`POST /api/v1/devices/{id}/revoke-token/`) by campus admins.
- Raw secret tokens are never exposed in standard API queries or logs.
- Unregistered devices or invalid tokens are rejected with `UNAUTHORIZED` status without crashing workers.

### 3. Background Workers & Startup Commands

Each service runs independently:

1. **MQTT Telemetry & ACK Subscriber Worker:**
   ```powershell
   python manage.py run_mqtt_subscriber
   ```
2. **MQTT Command Dispatcher Worker:**
   ```powershell
   python manage.py run_mqtt_command_worker --poll-interval 2.0 --timeout-seconds 30
   ```
3. **Simulated ESP32 IoT Node:**
   ```powershell
   python -m iot_simulator.run_simulator --hardware-id ESP32_LAB_101 --auth-token <SECRET_TOKEN>
   ```
4. **Daphne ASGI Web & WebSocket Server:**
   ```powershell
   daphne -b 127.0.0.1 -p 8000 config.asgi:application
   ```

### 4. WebSocket Real-Time Channels

Live campus streaming endpoints secured with JWT tokens via query param (`?token=<jwt_access_token>`):
- `ws://localhost:8000/ws/devices/?token=...`: Device status & relay updates.
- `ws://localhost:8000/ws/rooms/?token=...`: Campus room telemetry feeds.
- `ws://localhost:8000/ws/rooms/{room_id}/?token=...`: Single room telemetry feed.
- `ws://localhost:8000/ws/energy/?token=...`: Electrical power & energy consumption stream.
- `ws://localhost:8000/ws/alerts/?token=...`: AI anomaly & policy alerts stream.

*Note: Unauthenticated connections receive close code `4001`; non-staff/non-admin connections receive `4003`.*


