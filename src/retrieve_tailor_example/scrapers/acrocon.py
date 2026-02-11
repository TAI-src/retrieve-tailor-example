"""Scraper for Markus Wagner's publications page on acrocon.com."""

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from retrieve_tailor_example.models import Article

DEFAULT_URL = "https://www.acrocon.com/~wagner/publications.html"


class AcroconScraper:
    """Scrape structured Article metadata from an acrocon.com publications page."""

    def __init__(self, url: str = DEFAULT_URL) -> None:
        self._url = url

    def scrape(self) -> list[Article]:
        response = requests.get(self._url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        articles: list[Article] = []

        for dd in soup.find_all("dd"):
            h4 = dd.find("h4")
            venue = h4.get_text(strip=True) if h4 else ""

            title_span = dd.find("span", style=lambda s: s and "font-weight" in s)
            title = title_span.get_text(strip=True) if title_span else ""
            if not title:
                continue

            authors_span = dd.find("span", style=lambda s: s and "font-style" in s)
            if authors_span:
                authors_text = authors_span.get_text(" ", strip=True)
                authors_text = re.split(r"\s*Supervisors?:", authors_text)[0]
                parts = re.split(r",\s*and\s+|,\s*|\s+and\s+", authors_text)
                authors = [a.strip() for a in parts if a.strip()]
            else:
                authors = []

            links: dict[str, str] = {}
            pdf_url: str | None = None
            for a_tag in dd.find_all("a", href=True):
                href = a_tag["href"]
                full_url = urljoin(self._url, href)
                label = a_tag.get_text(strip=True)
                if label:
                    links[label] = full_url
                if href.lower().endswith(".pdf"):
                    pdf_url = full_url

            articles.append(
                Article(
                    title=title,
                    authors=authors,
                    venue=venue,
                    pdf_url=pdf_url,
                    links=links,
                )
            )

        return articles
