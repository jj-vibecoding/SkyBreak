# SkyBreak

**SkyBreak: Plan your quick airplane getaways**

A tool for planning short trips and weekend getaways by air.

## Features
- ✈️ **Airport Management** — Add, list, and delete monitored airports with IATA validation
- 🛫 **Flight Schedule** — Browse departures/arrivals with date filtering; fetch latest data on demand
- 🧳 **Trip Planning** — Search turnarounds (outbound + return) with configurable weekdays, times, and trip duration
- ⭐ **Favorites** — Save trips, track price history, view interactive charts
- 💰 **Price Monitoring** — Automatic background price checks at configurable intervals
- 🔍 **Saved Search Configs** — Save and reload named trip search configurations (server-side)
- 📱 **Responsive UI** — Works on desktop and mobile with localStorage persistence

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