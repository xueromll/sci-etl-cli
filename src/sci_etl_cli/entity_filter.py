from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sci_etl_core.llm.extraction_async import AsyncEntityExtractor
from sci_etl_core.processors.validation import RecordValidator


class ValidatingEntityExtractor(AsyncEntityExtractor):
    """Drop extracted entities that any validator rejects, logging each one."""

    def __init__(
        self,
        inner: AsyncEntityExtractor,
        validators: Sequence[RecordValidator],
        key_column: str,
        log: Callable[[str], None],
    ) -> None:
        self._inner = inner
        self._validators = tuple(validators)
        self._key_column = key_column
        self._log = log

    async def extract(self, text: str | bytes) -> list[dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        for entity in await self._inner.extract(text):
            rejected_by = next(
                (type(validator).__name__ for validator in self._validators if not validator.is_valid(entity)),
                None,
            )
            if rejected_by is None:
                accepted.append(entity)
            else:
                self._log(f"Entity {entity.get(self._key_column)!r} rejected by {rejected_by}")
        return accepted
