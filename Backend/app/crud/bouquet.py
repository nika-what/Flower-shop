from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bouquet import Bouquet
from app.schemas.bouquet import BouquetCreate, BouquetUpdate


class BouquetCRUD:
    async def list(
        self,
        db: AsyncSession,
        offset: int = 0,
        limit: int = 20,
        query: str | None = None,
        published_only: bool = False,
    ) -> list[Bouquet]:
        stmt = select(Bouquet)
        if query:
            like_query = f'%{query}%'
            stmt = stmt.where(or_(Bouquet.name.ilike(like_query), Bouquet.description.ilike(like_query)))
        if published_only:
            stmt = stmt.where(Bouquet.is_published.is_(True))
        stmt = stmt.offset(offset).limit(limit).order_by(Bouquet.id.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, bouquet_id: int) -> Bouquet | None:
        return await db.get(Bouquet, bouquet_id)

    async def create(self, db: AsyncSession, bouquet_in: BouquetCreate, user_id: int) -> Bouquet:
        bouquet = Bouquet(**bouquet_in.model_dump(), user_id=user_id)
        db.add(bouquet)
        await db.commit()
        await db.refresh(bouquet)
        return bouquet

    async def update(self, db: AsyncSession, bouquet: Bouquet, bouquet_in: BouquetUpdate) -> Bouquet:
        for key, value in bouquet_in.model_dump(exclude_unset=True).items():
            setattr(bouquet, key, value)
        await db.commit()
        await db.refresh(bouquet)
        return bouquet

    async def delete(self, db: AsyncSession, bouquet: Bouquet) -> None:
        await db.delete(bouquet)
        await db.commit()


bouquet_crud = BouquetCRUD()
