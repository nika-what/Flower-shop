from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flower import Flower
from app.schemas.flower import FlowerCreate, FlowerUpdate


class FlowerCRUD:
    async def list(
        self,
        db: AsyncSession,
        offset: int = 0,
        limit: int = 20,
        query: str | None = None,
        category: str | None = None,
    ) -> list[Flower]:
        stmt = select(Flower)
        if query:
            like_query = f'%{query}%'
            stmt = stmt.where(or_(Flower.name.ilike(like_query), Flower.latin_name.ilike(like_query)))
        if category:
            stmt = stmt.where(Flower.category.ilike(category))
        stmt = stmt.offset(offset).limit(limit).order_by(Flower.id.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, flower_id: int) -> Flower | None:
        return await db.get(Flower, flower_id)

    async def create(self, db: AsyncSession, flower_in: FlowerCreate) -> Flower:
        flower = Flower(**flower_in.model_dump())
        db.add(flower)
        await db.commit()
        await db.refresh(flower)
        return flower

    async def update(self, db: AsyncSession, flower: Flower, flower_in: FlowerUpdate) -> Flower:
        for key, value in flower_in.model_dump(exclude_unset=True).items():
            setattr(flower, key, value)
        await db.commit()
        await db.refresh(flower)
        return flower

    async def delete(self, db: AsyncSession, flower: Flower) -> None:
        await db.delete(flower)
        await db.commit()


flower_crud = FlowerCRUD()
