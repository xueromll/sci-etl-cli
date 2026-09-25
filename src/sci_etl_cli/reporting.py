from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from sci_etl_core.extractors.async_base import AsyncExtractor

if TYPE_CHECKING:
    from sci_etl_core import AsyncArxivExtractor
    from sci_etl_core.models import ListingPage, RawRecord


class ListingReporter(AsyncExtractor):
    """Log one line per listing page while delegating every call to ``inner``.

    ``inner`` pages by offset, so the reporter does too, and ``newest_first``
    runs keep working through it.
    """

    def __init__(self, inner: AsyncArxivExtractor, log: Callable[[str], None]) -> None:
        self._inner = inner
        self._log = log

    def cursor_for_offset(self, offset: int) -> str:
        return self._inner.cursor_for_offset(offset)

    async def fetch_page(self, query: str, cursor: str | None, page_size: int) -> ListingPage:
        page = await self._inner.fetch_page(query, cursor, page_size)
        if page.entries:
            self._log(f"Listing page at offset {cursor or 0}: {page.entries} entries")
        return page

    async def fetch_full_text(self, record: RawRecord) -> str:
        return await self._inner.fetch_full_text(record)
