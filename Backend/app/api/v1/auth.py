import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_email_code
from app.core.security import create_access_token, get_password_hash, verify_password
from app.crud.user import user_crud
from app.models.auth_code import AuthCode, AuthCodePurpose
from app.schemas.auth import (
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    VerifyEmailRequest,
)
from app.schemas.user import Token, User, UserCreate

router = APIRouter(prefix='/auth', tags=['auth'])


def _generate_code(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


@router.post('/register', response_model=dict, status_code=201)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> dict:
    existing = await user_crud.get_by_email(db, user_in.email)
    if existing:
        # If email already verified - don't allow re-registration.
        if existing.is_active:
            raise HTTPException(status_code=400, detail='Email already registered')

        # Reactivate existing user and update credentials.
        existing.full_name = user_in.full_name
        existing.hashed_password = get_password_hash(user_in.password)
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)

        return {'status': 'ok', 'user_id': existing.id, 'email': existing.email}
    else:
        user = await user_crud.create(db, user_in, is_active=True)
        return {'status': 'ok', 'user_id': user.id, 'email': user.email}


@router.post('/login', response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)) -> Token:
    user = await user_crud.get_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Incorrect email or password')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Email is not verified')

    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.post('/verify-email', response_model=dict)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    now = datetime.now(timezone.utc)

    stmt = (
        select(AuthCode)
        .where(
            AuthCode.email == payload.email,
            AuthCode.purpose == AuthCodePurpose.email_verify.value,
            AuthCode.used_at.is_(None),
            AuthCode.expires_at > now,
        )
        .order_by(AuthCode.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    code_row = result.scalars().first()

    if not code_row:
        raise HTTPException(status_code=400, detail='Invalid or expired code')

    if not verify_password(payload.code, code_row.code_hash):
        raise HTTPException(status_code=400, detail='Invalid or expired code')

    code_row.used_at = now

    user = await user_crud.get_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    user.is_active = True

    await db.commit()
    return {'status': 'ok'}


@router.post('/password-reset/request', response_model=dict)
async def password_reset_request(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    # Don't leak whether email exists.
    user = await user_crud.get_by_email(db, payload.email)
    if not user:
        return {'status': 'ok'}

    code = _generate_code()
    code_hash = get_password_hash(code)
    auth_code = AuthCode.from_purpose_and_code(
        email=payload.email,
        purpose=AuthCodePurpose.password_reset,
        code_hash=code_hash,
        expires_in_minutes=settings.EMAIL_CODE_EXPIRE_MINUTES,
    )
    auth_code.user_id = user.id

    db.add(auth_code)
    await db.commit()

    sent = send_email_code(payload.email, purpose=AuthCodePurpose.password_reset.value, code=code)
    if not sent and settings.EMAIL_DEBUG_RETURN_CODE:
        return {'status': 'ok', 'debug_code': code}

    return {'status': 'ok'}


@router.post('/password-reset/confirm', response_model=dict)
async def password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(AuthCode)
        .where(
            AuthCode.email == payload.email,
            AuthCode.purpose == AuthCodePurpose.password_reset.value,
            AuthCode.used_at.is_(None),
            AuthCode.expires_at > now,
        )
        .order_by(AuthCode.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    code_row = result.scalars().first()

    if not code_row:
        raise HTTPException(status_code=400, detail='Invalid or expired code')

    if not verify_password(payload.code, code_row.code_hash):
        raise HTTPException(status_code=400, detail='Invalid or expired code')

    code_row.used_at = now

    user = await user_crud.get_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()

    return {'status': 'ok'}
