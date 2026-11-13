# Florist Shop Backend (FastAPI)

Production-ready backend skeleton for a florist e-commerce service with JWT auth, PostgreSQL, Alembic migrations, AI bouquet generation mock endpoint, and Docker setup.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 async (`asyncpg`)
- PostgreSQL + Alembic migrations
- JWT auth (`OAuth2PasswordBearer`)
- Redis (optional cache foundation)
- SlowAPI rate limiting
- Pytest + HTTPX tests

## Run with Docker

1. Copy env:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker-compose up --build
```

3. Open:
- API: http://localhost:8000
- Docs (Swagger): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/health

## Main Endpoints

- Auth:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
- Flowers:
  - `GET /api/v1/flowers`
  - `POST /api/v1/flowers` (admin)
  - `PUT /api/v1/flowers/{id}` (admin)
  - `DELETE /api/v1/flowers/{id}` (admin)
- Bouquets:
  - `GET /api/v1/bouquets`
  - `POST /api/v1/bouquets`
  - `GET /api/v1/bouquets/{id}`
  - `PUT /api/v1/bouquets/{id}`
  - `DELETE /api/v1/bouquets/{id}`
- Orders (authorized only):
  - `GET /api/v1/orders`
  - `POST /api/v1/orders`
- AI integration:
  - `POST /api/v1/ai/generate-bouquet`
  - `GET /api/v1/ai/flowers`

## Notes

- First launch auto-creates admin from `.env`:
  - `FIRST_SUPERUSER_EMAIL`
  - `FIRST_SUPERUSER_PASSWORD`
- Order statuses: `new`, `processing`, `paid`, `delivered`
- Flower and bouquet endpoints support `offset`/`limit` pagination and search filters.

## Local (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Run tests

```bash
pytest -q
```
