from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.crud.flower import flower_crud
from app.models.user import User
from app.schemas.flower import Flower, FlowerCreate, FlowerUpdate

router = APIRouter(prefix='/flowers', tags=['flowers'])


@router.get('', response_model=list[Flower])
async def list_flowers(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    query: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Flower]:
    return await flower_crud.list(db, offset=offset, limit=limit, query=query, category=category)


@router.post('', response_model=Flower, status_code=201)
async def create_flower(
    flower_in: FlowerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Flower:
    return await flower_crud.create(db, flower_in)


@router.put('/{flower_id}', response_model=Flower)
async def update_flower(
    flower_id: int,
    flower_in: FlowerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Flower:
    flower = await flower_crud.get(db, flower_id)
    if not flower:
        raise HTTPException(status_code=404, detail='Flower not found')
    return await flower_crud.update(db, flower, flower_in)


@router.delete('/{flower_id}', status_code=204)
async def delete_flower(
    flower_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> None:
    flower = await flower_crud.get(db, flower_id)
    if not flower:
        raise HTTPException(status_code=404, detail='Flower not found')
    await flower_crud.delete(db, flower)
