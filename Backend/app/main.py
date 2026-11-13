from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import ai_router, auth_router, bouquets_router, flowers_router, geo_router, orders_router, users_router
from app.models.auth_code import AuthCode  # noqa: F401
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.crud.user import user_crud
from app.schemas.user import UserCreate

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        admin = await user_crud.get_by_email(db, settings.FIRST_SUPERUSER_EMAIL)
        if not admin:
            await user_crud.create(
                db,
                UserCreate(
                    email=settings.FIRST_SUPERUSER_EMAIL,
                    full_name='Admin',
                    password=settings.FIRST_SUPERUSER_PASSWORD,
                ),
                is_admin=True,
            )
    yield


app = FastAPI(title=settings.PROJECT_NAME, version='1.0.0', lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/health', tags=['health'])
@limiter.limit('30/minute')
async def healthcheck(request: Request) -> dict[str, str]:
    _ = request
    return {'status': 'ok'}


app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(flowers_router, prefix=settings.API_V1_STR)
app.include_router(bouquets_router, prefix=settings.API_V1_STR)
app.include_router(orders_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(geo_router, prefix=settings.API_V1_STR)
