from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from backend.core.config import get_settings

ModelT = TypeVar("ModelT")


def clamp_query_window(skip: int = 0, limit: int | None = None) -> tuple[int, int]:
    """Normalize pagination inputs to avoid accidental expensive queries."""
    settings = get_settings()
    normalized_skip = max(0, skip)
    requested_limit = settings.default_page_size if limit is None else limit
    normalized_limit = max(1, min(requested_limit, settings.max_page_size))
    return normalized_skip, normalized_limit


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT], db: Session):
        self.model = model
        self.db = db

    def get(self, item_id: int) -> ModelT | None:
        return self.db.get(self.model, item_id)

    def list(self, skip: int = 0, limit: int = 100) -> list[ModelT]:
        skip, limit = clamp_query_window(skip, limit)
        return list(self.db.query(self.model).offset(skip).limit(limit).all())

    def count(self) -> int:
        return int(self.db.query(self.model).count())

    def add(self, instance: ModelT) -> ModelT:
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        self.db.delete(instance)
        self.db.commit()
