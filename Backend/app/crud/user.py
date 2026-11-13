from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate


class UserCRUD:
    async def get_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        return await db.get(User, user_id)

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        user_in: UserCreate,
        is_admin: bool = False,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=get_password_hash(user_in.password),
            is_admin=is_admin,
            is_active=is_active,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


user_crud = UserCRUD()
