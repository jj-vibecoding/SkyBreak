# SkyBreak

**SkyBreak: Plan your quick airplane getaways**

A tool for planning short trips and weekend getaways by air.

## Features
- ✈️ Flight schedule browsing (departures & arrivals) with date filtering
- 💰 Price tracking for favorite trips, including price history chart
- 📅 Trip planning with minimum trip length and turnaround (return-flight) matching
- 📍 Monitored airports with automatic periodic flight fetching (background scheduler)

## Quick Start (Docker — recommended)
```bash
git clone https://github.com/jj-vibecoding/SkyBreak.git
cd SkyBreak
docker compose up -d --build
```
The app is served on http://localhost:8088 (API + frontend, single container).
Flight data and settings persist in the mounted `/data` volume.

## Development Setup
```bash
# Backend
pip install -r requirements-dev.txt
python -m skybreak.app          # API on port 5000, DB via DB_FILE env var

# Frontend (dev server)
cd frontend && npm install && npm start
```

## Tests
```bash
python -m pytest tests/ -v --tb=short
```

## License
MIT