"""Scraper protocol — the data-source abstraction layer."""

from typing import Protocol, runtime_checkable

from retrieve_tailor_example.models import Article


@runtime_checkable
class Scraper(Protocol):
    def scrape(self) -> list[Article]: ...
