from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from sci_etl_core.extractors.async_base import AsyncExtractor, OffsetListing

if TYPE_CHECKING:
    from sci_etl_core.models import ListingPage, RawRecord


class ListingReporter(AsyncExtractor):
    """Log one line per listing page while delegating every call to ``inner``.

    Pages are numbered from 1 in the order they are fetched, since a source
    that pages by opaque cursor has no offsets to report. Build one with
    :func:`listing_reporter`, which keeps an ``OffsetListing`` inner extractor
    one.
    """

    def __init__(self, inner: AsyncExtractor, log: Callable[[str], None]) -> None:
        self._inner = inner
        self._log = log
        self._pages = 0

    async def fetch_page(self, query: str, cursor: str | None, page_size: int) -> ListingPage:
        page = await self._inner.fetch_page(query, cursor, page_size)
        self._pages += 1
        if page.entries:
            self._log(f"Listing page {self._describe(cursor)}: {page.entries} entries")
        return page

    async def fetch_full_text(self, record: RawRecord) -> str:
        return await self._inner.fetch_full_text(record)

    def _describe(self, cursor: str | None) -> str:
        return str(self._pages)


class OffsetListingReporter(ListingReporter):
    """A :class:`ListingReporter` over an ``OffsetListing``, which it stays, so ``newest_first`` runs keep working."""

    def __init__(self, inner: AsyncExtractor, offsets: OffsetListing, log: Callable[[str], None]) -> None:
        super().__init__(inner, log)
        self._offsets = offsets

    def cursor_for_offset(self, offset: int) -> str:
        return self._offsets.cursor_for_offset(offset)

    def _describe(self, cursor: str | None) -> str:
        return f"at offset {cursor or 0}"


def listing_reporter(inner: AsyncExtractor, log: Callable[[str], None]) -> ListingReporter:
    """Wrap ``inner`` in the reporter that forwards ``cursor_for_offset`` only when ``inner`` has it."""
    if isinstance(inner, OffsetListing):
        return OffsetListingReporter(inner, inner, log)
    return ListingReporter(inner, log)
