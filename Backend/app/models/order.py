from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    new = 'new'
    processing = 'processing'
    paid = 'paid'
    delivered = 'delivered'


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    bouquet_id: Mapped[int] = mapped_column(ForeignKey('bouquets.id', ondelete='CASCADE'), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.new, nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_marked_complete_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user = relationship('User', back_populates='orders')
    bouquet = relationship('Bouquet', back_populates='orders')
