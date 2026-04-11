from typing import Any

from pydantic import BaseModel


class PaginationMeta(BaseModel):
    total_pages: int
    next_page: int | None
    previous_page: int | None
    page: int
    limit: int


class ListResponse(BaseModel):
    data: list[Any]
    pagination: PaginationMeta
