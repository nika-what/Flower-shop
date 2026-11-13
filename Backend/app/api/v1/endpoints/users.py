from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import User as UserSchema

router = APIRouter(prefix='/users', tags=['users'])


@router.get('/me', response_model=UserSchema)
async def read_me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


@router.delete('/me', status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    db.delete(current_user)
    await db.commit()
    return None
