from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.order import OrderStatus


class OrderCreate(BaseModel):
    bouquet_id: int
    quantity: int = 1
    delivery_address: str = Field(..., min_length=3, max_length=500)
    user_comment: str | None = Field(default=None, max_length=2000)


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    bouquet_id: int
    quantity: int
    total_price: float
    status: OrderStatus
    delivery_address: str
    user_comment: str | None = None
    created_at: datetime


class OrderPublic(BaseModel):
    """Заказ для клиента и админа: номер, букет, комментарий."""

    id: int
    user_id: int
    bouquet_id: int
    quantity: int
    total_price: float
    status: OrderStatus
    delivery_address: str
    user_comment: str | None = None
    created_at: datetime
    bouquet_name: str = ''
    bouquet_image_url: str | None = None
    admin_marked_complete_at: datetime | None = None

    @computed_field
    @property
    def order_number(self) -> str:
        return f'№{self.id:06d}'

    @computed_field
    @property
    def progress_status(self) -> str:
        return 'Готово' if self.admin_marked_complete_at else 'В работе'


class AdminOrderPublic(OrderPublic):
    customer_email: str = ''
    customer_full_name: str = ''


class AdminOrderCompleteIn(BaseModel):
    completed: bool
