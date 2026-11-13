from pydantic import BaseModel, ConfigDict


class BouquetBase(BaseModel):
    name: str
    description: str | None = None
    price: float
    flowers: dict
    image_url: str | None = None
    is_published: bool = False


class BouquetCreate(BouquetBase):
    pass


class BouquetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    flowers: dict | None = None
    image_url: str | None = None
    is_published: bool | None = None


class Bouquet(BouquetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
