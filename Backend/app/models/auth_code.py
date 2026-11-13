from datetime import datetime, timedelta, timezone
import enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthCodePurpose(str, enum.Enum):
    email_verify = 'email_verify'
    password_reset = 'password_reset'


class AuthCode(Base):
    __tablename__ = 'auth_codes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # We store email to support reset flow even if user_id is unknown.
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    purpose: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Hash of the 6-digit code (stored using passlib bcrypt via get_password_hash()).
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional relation back to user.
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    def is_expired(self) -> bool:
        return self.expires_at <= datetime.now(timezone.utc)

    @classmethod
    def from_purpose_and_code(cls, *, email: str, purpose: AuthCodePurpose, code_hash: str, expires_in_minutes: int) -> 'AuthCode':
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
        return cls(
            email=email,
            purpose=str(purpose.value),
            code_hash=code_hash,
            expires_at=expires_at,
        )

