# Surakshanet

Intelligent Transportation System MVP for smart traffic monitoring and control.

## Quick Start

Make sure you have Docker and Docker Compose installed.

1. Clone the repository
2. Set up the environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start the development environment:
   ```bash
   cd infra
   docker-compose up -d
   ```

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, PyTorch
- **Frontend**: TypeScript, React, TailwindCSS
- **Database**: PostgreSQL with PostGIS, TimescaleDB
- **Cache & Message Broker**: Redis, Mosquitto (MQTT)
- **Monitoring**: Prometheus, Grafana

## Project Structure

- `backend/`: FastAPI application and ML models
- `frontend/`: React dashboards and user interfaces
- `infra/`: Docker compose and infrastructure configurations

## License

MIT
