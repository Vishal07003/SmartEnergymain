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

