from app.api.v1.auth import router as auth_router
from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.bouquets import router as bouquets_router
from app.api.v1.endpoints.flowers import router as flowers_router
from app.api.v1.endpoints.geo import router as geo_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.users import router as users_router

__all__ = [
    'auth_router',
    'ai_router',
    'bouquets_router',
    'flowers_router',
    'geo_router',
    'orders_router',
    'users_router',
]
