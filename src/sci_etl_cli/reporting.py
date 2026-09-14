from __future__ import annotations

from typing import Callable

from sci_etl_core.extractors.async_base import AsyncExtractor
from sci_etl_core.models import RawRecord


class ListingReporter(AsyncExtractor):
    """Log one line per listing page while delegating every call to ``inner``."""

    def __init__(self, inner: AsyncExtractor, log: Callable[[str], None]) -> None:
        self._inner = inner
        self._log = log
        self._start_index = 0

    async def search(self, query: str, max_results: int, start_index: int) -> bytes | None:
        self._start_index = start_index
        return await self._inner.search(query, max_results, start_index)

    def parse_listing(self, raw_listing: bytes, seen_ids: set[str]) -> tuple[list[RawRecord], int]:
        records, entries = self._inner.parse_listing(raw_listing, seen_ids)
        if entries:
            self._log(
                f"Listing page at offset {self._start_index}: {entries} entries, {len(records)} to process"
            )
        return records, entries

    async def fetch_full_text(self, record: RawRecord) -> str:
        return await self._inner.fetch_full_text(record)
