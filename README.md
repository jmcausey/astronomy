# Astronomy

Standalone astronomy service migrated from `jmcausey/localservices`.

Features:
- IPGeolocation Astronomy API collection
- PostgreSQL persistence on the shared `cl_shared_data` network
- Location filtering
- NASA APOD API endpoint
- 24-hour solar/lunar celestial dial generation
- Current moon phase image generation
- Hourly collection scheduler

Configure `IPGEOLOCATION_API_KEY` and shared PostgreSQL credentials in `.env`.

Run:

```bash
docker compose up -d --build
```

Web UI: http://localhost:5003/astronomy
