"""PDF extraction and fetch utilities."""

import tempfile
from pathlib import Path

import pymupdf
import requests


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract text from a local PDF file."""
    doc = pymupdf.open(pdf_path)
    text = "\n".join(str(page.get_text()) for page in doc)
    doc.close()
    return text


def fetch_and_extract(url: str) -> str:
    """Download a PDF from a URL to a temp file, then extract its text."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name
    return extract_text_from_pdf(tmp_path)
