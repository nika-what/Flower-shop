from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.crud.user import user_crud
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')
oauth2_optional = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login', auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
    )
    try:
        payload = decode_token(token)
        user_id = int(payload.get('sub'))
    except Exception:
        raise credentials_exception

    user = await user_crud.get_by_id(db, user_id)
    if not user:
        raise credentials_exception
    return user


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_optional),
) -> User | None:
    """
    Если токена нет или он недействителен — None (гость), без 401.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = int(payload.get('sub'))
    except Exception:
        return None
    user = await user_crud.get_by_id(db, user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail='Inactive user')
    return current_user


async def get_current_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail='Admin privileges required')
    return current_user
