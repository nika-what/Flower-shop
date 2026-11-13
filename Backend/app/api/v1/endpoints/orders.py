from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_admin
from app.core.database import get_db
from app.crud.order import order_crud
from app.models.user import User
from app.schemas.order import AdminOrderCompleteIn, AdminOrderPublic, OrderCreate, OrderPublic

router = APIRouter(prefix='/orders', tags=['orders'])


@router.patch('/{order_id}/admin-complete', response_model=AdminOrderPublic)
async def patch_order_admin_complete(
    order_id: int,
    body: AdminOrderCompleteIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminOrderPublic:
    """Отметить заказ выполненным (или снять отметку). Выполненные скрываются после 5 новых заказов."""
    order = await order_crud.set_admin_completed(db, order_id, body.completed)
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    return await order_crud.to_admin_order_public(db, order)


@router.get('/admin', response_model=list[AdminOrderPublic])
async def list_orders_admin(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[AdminOrderPublic]:
    """Все заказы для администратора (номер, букет, комментарий клиента)."""
    return await order_crud.list_public_for_admin(db, offset=offset, limit=limit)


@router.get('', response_model=list[OrderPublic])
async def list_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[OrderPublic]:
    return await order_crud.list_public_for_user(db, current_user.id, offset=offset, limit=limit)


@router.post('', response_model=OrderPublic, status_code=201)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OrderPublic:
    order = await order_crud.create(db, current_user.id, order_in)
    if not order:
        raise HTTPException(status_code=404, detail='Bouquet not found')
    return await order_crud.to_order_public(db, order)
