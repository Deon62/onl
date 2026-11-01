from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.services.normalize import normalize_domain, normalize_phone

T = TypeVar("T")


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class Page(Schema, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def _phone(v: str) -> str:
    if v == "":
        return v
    n = normalize_phone(v)
    if n is None:
        raise ValueError("Enter a valid Kenyan phone number, e.g. 0712 345 678")
    return n


def _domain(v: str) -> str:
    n = normalize_domain(v)
    if n is None:
        raise ValueError("Enter a valid domain, e.g. example.co.ke")
    return n


# Normalised on input: "0712 345 678" -> "254712345678"; "" allowed (not provided yet)
KenyanPhone = Annotated[str, AfterValidator(_phone)]
Domain = Annotated[str, AfterValidator(_domain)]


class Message(Schema):
    message: str
