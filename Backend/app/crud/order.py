from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bouquet import Bouquet
from app.models.order import Order
from app.models.user import User
from app.schemas.order import AdminOrderPublic, OrderCreate, OrderPublic


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class OrderCRUD:
    async def list_for_user(self, db: AsyncSession, user_id: int, offset: int = 0, limit: int = 20) -> list[Order]:
        stmt = select(Order).where(Order.user_id == user_id).offset(offset).limit(limit).order_by(Order.id.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _admin_public(
        self,
        o: Order,
        bname: str | None,
        bimg: str | None,
        email: str | None,
        full_name: str | None,
    ) -> AdminOrderPublic:
        return AdminOrderPublic(
            id=o.id,
            user_id=o.user_id,
            bouquet_id=o.bouquet_id,
            quantity=o.quantity,
            total_price=float(o.total_price),
            status=o.status,
            delivery_address=o.delivery_address,
            user_comment=o.user_comment,
            created_at=o.created_at,
            bouquet_name=str(bname or ''),
            bouquet_image_url=str(bimg) if bimg else None,
            customer_email=str(email or ''),
            customer_full_name=str(full_name or ''),
            admin_marked_complete_at=o.admin_marked_complete_at,
        )

    async def list_public_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[OrderPublic]:
        stmt = (
            select(Order, Bouquet.name, Bouquet.image_url)
            .join(Bouquet, Order.bouquet_id == Bouquet.id)
            .where(Order.user_id == user_id)
            .order_by(Order.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        out: list[OrderPublic] = []
        for row in result.all():
            o, bname, bimg = row[0], row[1], row[2]
            out.append(
                OrderPublic(
                    id=o.id,
                    user_id=o.user_id,
                    bouquet_id=o.bouquet_id,
                    quantity=o.quantity,
                    total_price=float(o.total_price),
                    status=o.status,
                    delivery_address=o.delivery_address,
                    user_comment=o.user_comment,
                    created_at=o.created_at,
                    bouquet_name=str(bname or ''),
                    bouquet_image_url=str(bimg) if bimg else None,
                    admin_marked_complete_at=o.admin_marked_complete_at,
                )
            )
        return out

    async def list_public_for_admin(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AdminOrderPublic]:
        """
        Заказы для админки. Отмеченные «выполнен» скрываются после появления 5 новых заказов
        (созданных позже момента отметки admin_marked_complete_at).
        """
        times_res = await db.execute(select(Order.id, Order.created_at))
        created_list: list[tuple[int, datetime]] = [(int(r[0]), r[1]) for r in times_res.all()]

        def count_orders_created_after(ts: datetime) -> int:
            tsu = _utc(ts)
            return sum(1 for _oid, ct in created_list if _utc(ct) > tsu)

        stmt = (
            select(Order, Bouquet.name, Bouquet.image_url, User.email, User.full_name)
            .join(Bouquet, Order.bouquet_id == Bouquet.id)
            .join(User, Order.user_id == User.id)
            .order_by(Order.id.desc())
            .limit(500)
        )
        result = await db.execute(stmt)
        visible: list[AdminOrderPublic] = []
        for row in result.all():
            o, bname, bimg, email, full_name = row[0], row[1], row[2], row[3], row[4]
            if o.admin_marked_complete_at is not None:
                if count_orders_created_after(o.admin_marked_complete_at) >= 5:
                    continue
            visible.append(self._admin_public(o, bname, bimg, email, full_name))

        return visible[offset : offset + limit]

    async def set_admin_completed(self, db: AsyncSession, order_id: int, completed: bool) -> Order | None:
        order = await db.get(Order, order_id)
        if not order:
            return None
        order.admin_marked_complete_at = datetime.now(timezone.utc) if completed else None
        await db.commit()
        await db.refresh(order)
        return order

    async def to_admin_order_public(self, db: AsyncSession, order: Order) -> AdminOrderPublic:
        stmt = (
            select(Bouquet.name, Bouquet.image_url, User.email, User.full_name)
            .select_from(Order)
            .join(Bouquet, Order.bouquet_id == Bouquet.id)
            .join(User, Order.user_id == User.id)
            .where(Order.id == order.id)
        )
        row = (await db.execute(stmt)).one_or_none()
        if not row:
            return self._admin_public(order, None, None, None, None)
        bname, bimg, email, full_name = row[0], row[1], row[2], row[3]
        return self._admin_public(order, bname, bimg, email, full_name)

    async def create(self, db: AsyncSession, user_id: int, order_in: OrderCreate) -> Order | None:
        bouquet = await db.get(Bouquet, order_in.bouquet_id)
        if not bouquet:
            return None
        total = Decimal(str(bouquet.price)) * order_in.quantity
        raw_comment = (order_in.user_comment or '').strip()
        comment = raw_comment[:2000] if raw_comment else None
        order = Order(
            user_id=user_id,
            bouquet_id=order_in.bouquet_id,
            quantity=order_in.quantity,
            total_price=float(total),
            delivery_address=order_in.delivery_address.strip()[:500],
            user_comment=comment,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def to_order_public(self, db: AsyncSession, order: Order) -> OrderPublic:
        bouquet = await db.get(Bouquet, order.bouquet_id)
        return OrderPublic(
            id=order.id,
            user_id=order.user_id,
            bouquet_id=order.bouquet_id,
            quantity=order.quantity,
            total_price=float(order.total_price),
            status=order.status,
            delivery_address=order.delivery_address,
            user_comment=order.user_comment,
            created_at=order.created_at,
            bouquet_name=str(bouquet.name) if bouquet else '',
            bouquet_image_url=str(bouquet.image_url) if bouquet and bouquet.image_url else None,
            admin_marked_complete_at=order.admin_marked_complete_at,
        )


order_crud = OrderCRUD()
