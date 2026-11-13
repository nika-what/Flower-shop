from pydantic import BaseModel, ConfigDict


class FlowerBase(BaseModel):
    name: str
    latin_name: str
    color: str
    price_per_unit: float
    description: str | None = None
    image_url: str | None = None
    category: str


class FlowerCreate(FlowerBase):
    pass


class FlowerUpdate(BaseModel):
    name: str | None = None
    latin_name: str | None = None
    color: str | None = None
    price_per_unit: float | None = None
    description: str | None = None
    image_url: str | None = None
    category: str | None = None


class Flower(FlowerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
