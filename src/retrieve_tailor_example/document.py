"""PDF extraction, download utilities, and batch conversion."""

import re
import tempfile
from pathlib import Path

import pymupdf
import requests
from rich.console import Console

from retrieve_tailor_example.models import Article

console = Console()


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:80]


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


def download_pdf(url: str, output_dir: Path) -> Path | None:
    """Download a single PDF to output_dir. Skips if file exists. Returns the path or None on failure."""
    filename = url.split("/")[-1]
    output_path = output_dir / filename

    if output_path.exists():
        console.print(f"  Skipping (exists): {filename}")
        return output_path

    try:
        with console.status(f"  Downloading: {filename}..."):
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            output_path.write_bytes(response.content)
        console.print(
            f"  Downloaded: {filename} ({len(response.content) / 1024:.1f} KB)"
        )
        return output_path
    except requests.RequestException as e:
        console.print(f"  Failed: {filename} ({e})")
        return None


def resolve_article_text(article: Article, md_dir: Path | None) -> str:
    """Get a paper's text: prefer a cached .md file, fall back to PDF URL."""
    if md_dir is not None and article.pdf_url:
        stem = Path(article.pdf_url.split("/")[-1]).stem
        md_path = md_dir / f"{stem}.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
    if article.pdf_url is None:
        raise ValueError(f"Article '{article.title}' has no pdf_url and no cached .md")
    return fetch_and_extract(article.pdf_url)


def convert_all_pdfs(
    input_dir: str | Path = "pdfs", output_dir: str | Path = "pdfs_as_md"
) -> list[Path]:
    """Convert every PDF in input_dir to a .md text file in output_dir."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        console.print(f"No PDFs found in {input_dir}/")
        return []

    console.print(f"Found {len(pdf_files)} PDFs in {input_dir}/\n")

    converted: list[Path] = []
    for i, pdf_path in enumerate(pdf_files, 1):
        md_path = output_dir / f"{pdf_path.stem}.md"

        if md_path.exists():
            console.print(f"[{i}/{len(pdf_files)}] Skipping (exists): {md_path.name}")
            converted.append(md_path)
            continue

        try:
            with console.status(
                f"[{i}/{len(pdf_files)}] Converting: {pdf_path.name}..."
            ):
                text = extract_text_from_pdf(pdf_path)
                md_path.write_text(text, encoding="utf-8")
            console.print(
                f"[{i}/{len(pdf_files)}] Converted: {pdf_path.name} -> {md_path.name} ({len(text)} chars)"
            )
            converted.append(md_path)
        except Exception as e:
            console.print(f"[{i}/{len(pdf_files)}] Failed: {pdf_path.name} ({e})")

    console.print(f"\nDone: {len(converted)}/{len(pdf_files)} files in {output_dir}/")
    return converted
