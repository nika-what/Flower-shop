from pydantic import BaseModel, Field


class AddressValidateIn(BaseModel):
    address: str = Field(..., min_length=3, max_length=500)


class AddressValidateOut(BaseModel):
    ok: bool
    normalized_address: str | None = None
    message: str | None = None


class AddressSuggestOut(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
