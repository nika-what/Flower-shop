from sqlalchemy import JSON, Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Bouquet(Base):
    __tablename__ = 'bouquets'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    flowers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    creator = relationship('User', back_populates='bouquets')
    orders = relationship('Order', back_populates='bouquet', cascade='all, delete-orphan')
