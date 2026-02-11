"""Unified CLI with subcommands: scrape, convert, classify, generate."""

import re
import time
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from retrieve_tailor_example.agents.anthropic import AnthropicAgent, DEFAULT_MODEL
from rich.console import Console

from retrieve_tailor_example.document import (
    convert_all_pdfs,
    download_pdf,
    resolve_article_text,
    slugify,
    fetch_and_extract,
)
from retrieve_tailor_example.models import Article
from retrieve_tailor_example.scrapers.acrocon import AcroconScraper
from retrieve_tailor_example.tasks.classify import classify_all_papers
from retrieve_tailor_example.tasks.generate import (
    generate_all_examples,
    generate_example,
)
from retrieve_tailor_example.tasks.classify import classify_paper

app = typer.Typer(
    name="retrieve-tailor-example",
    help="Scrape, convert, classify, and generate example summaries for publications.",
)


def _extract_metadata_from_generated_content(content: str) -> dict[str, str]:
    """Extract title, authors, and other metadata from generated markdown frontmatter."""
    # Extract YAML frontmatter
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not frontmatter_match:
        return {}

    frontmatter = frontmatter_match.group(1)
    metadata = {}

    # Extract title
    title_match = re.search(r"title:\s*(.+)", frontmatter)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    # Extract authors (handle both single and list format)
    authors_match = re.search(r"authors:\s*\n((?:\s*-\s*.+\n)+)", frontmatter)
    if authors_match:
        authors_text = authors_match.group(1)
        authors = [
            line.strip().replace("- ", "")
            for line in authors_text.split("\n")
            if line.strip()
        ]
        metadata["authors"] = authors
    else:
        # Try single line format
        authors_match = re.search(r"authors:\s*(.+)", frontmatter)
        if authors_match:
            metadata["authors"] = [authors_match.group(1).strip()]

    # Extract date/venue info
    date_match = re.search(r"date:\s*(.+)", frontmatter)
    if date_match:
        metadata["date"] = date_match.group(1).strip()

    return metadata


@app.command()
def scrape(
    url: Annotated[
        str,
        typer.Option(help="Publications page URL"),
    ] = "https://www.acrocon.com/~wagner/publications.html",
    pdf_dir: Annotated[
        str,
        typer.Option(help="Directory to save PDFs"),
    ] = "pdfs",
    articles_dir: Annotated[
        str,
        typer.Option(help="Directory to save article JSONs"),
    ] = "articles",
    delay: Annotated[
        float,
        typer.Option(help="Delay between downloads in seconds"),
    ] = 0.5,
) -> None:
    """Scrape articles, download PDFs, and save article JSONs."""
    pdf_path = Path(pdf_dir)
    articles_path = Path(articles_dir)
    pdf_path.mkdir(parents=True, exist_ok=True)
    articles_path.mkdir(parents=True, exist_ok=True)

    console = Console()
    scraper = AcroconScraper(url=url)
    with console.status(f"Scraping articles from {url}..."):
        articles = scraper.scrape()
    console.print(f"Found {len(articles)} articles.\n")

    downloaded = 0
    for i, article in enumerate(articles, 1):
        if article.pdf_url:
            stem = Path(article.pdf_url.split("/")[-1]).stem
        else:
            stem = slugify(article.title)

        json_path = articles_path / f"{stem}.json"
        if not json_path.exists():
            article.save(json_path)

        if article.pdf_url:
            console.print(f"[{i}/{len(articles)}] {article.title[:60]}...")
            path = download_pdf(article.pdf_url, pdf_path)
            if path is not None:
                downloaded += 1
            if i < len(articles):
                time.sleep(delay)

    console.print(
        f"\nDone: {downloaded} PDFs downloaded, {len(articles)} article JSONs in {articles_path}/"
    )


@app.command()
def convert(
    input_dir: Annotated[
        str,
        typer.Option("-i", "--input-dir", help="Directory with PDFs"),
    ] = "pdfs",
    output_dir: Annotated[
        str,
        typer.Option("-o", "--output-dir", help="Output directory"),
    ] = "pdfs_as_md",
) -> None:
    """Convert all PDFs in a directory to .md text files."""
    convert_all_pdfs(input_dir=input_dir, output_dir=output_dir)


@app.command()
def classify(
    input_dir: Annotated[
        str,
        typer.Option("-i", "--input-dir", help="Directory with .md files"),
    ] = "pdfs_as_md",
    output: Annotated[
        str,
        typer.Option("-o", "--output", help="Output JSON path"),
    ] = "real_world_papers.json",
    model: Annotated[
        str,
        typer.Option(help="Model to use"),
    ] = "claude-haiku-4-5-20251001",
    delay: Annotated[
        float,
        typer.Option(help="Delay between API calls in seconds"),
    ] = 0.2,
) -> None:
    """Classify papers as real-world application papers or not."""
    load_dotenv()
    agent = AnthropicAgent(model=model)
    classify_all_papers(
        md_dir=input_dir,
        agent=agent,
        output_path=output,
        delay=delay,
    )


@app.command()
def generate(
    article_path: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--article-path",
            help="Path to a single article JSON (overrides --articles-dir and --classifications)",
        ),
    ] = None,
    articles_dir: Annotated[
        str,
        typer.Option(
            "-a", "--articles-dir", help="Directory with article JSON metadata"
        ),
    ] = "articles",
    classifications: Annotated[
        str,
        typer.Option("-c", "--classifications", help="Path to classifications JSON"),
    ] = "ignore_me/real_world_papers.json",
    md_dir: Annotated[
        str,
        typer.Option(
            "-m", "--md-dir", help="Directory with pre-converted .md paper texts"
        ),
    ] = "pdfs_as_md",
    output_dir: Annotated[
        str,
        typer.Option("-o", "--output-dir", help="Output directory for examples"),
    ] = "examples",
    model: Annotated[
        str,
        typer.Option(help=f"Model to use (default: {DEFAULT_MODEL})"),
    ] = DEFAULT_MODEL,
    delay: Annotated[
        float,
        typer.Option(help="Delay between API calls in seconds"),
    ] = 1.0,
) -> None:
    """Generate example summaries for real-world application papers."""
    load_dotenv()
    agent = AnthropicAgent(model=model)

    if article_path is not None:
        article_file = Path(article_path)
        if not article_file.exists():
            print(f"Error: article not found: {article_path}")
            raise typer.Exit(code=1)

        md_dir_path = Path(md_dir)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        console = Console()
        article = Article.load(article_file)
        text = resolve_article_text(article, md_dir_path)
        with console.status(f"Generating example for: {article.title[:80]}..."):
            result = generate_example(article, text, paper_id=1, agent=agent)
        output_path = out_dir / f"{article_file.stem}.md"
        output_path.write_text(result, encoding="utf-8")
        console.print(f"Saved to {output_path}")
    else:
        generate_all_examples(
            articles_dir=articles_dir,
            classifications_path=classifications,
            md_dir=md_dir,
            output_dir=output_dir,
            agent=agent,
            delay=delay,
        )


@app.command()
def generate_from_url(
    url: Annotated[
        str,
        typer.Argument(help="URL of a single PDF or paper to process"),
    ],
    output_file: Annotated[
        str,
        typer.Option("-o", "--output", help="Output markdown file path"),
    ] = "generated_example.md",
    model: Annotated[
        str,
        typer.Option(help=f"Model to use (default: {DEFAULT_MODEL})"),
    ] = DEFAULT_MODEL,
    force_generate: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Generate example even if not classified as real-world application",
        ),
    ] = False,
) -> None:
    """Generate an example from a single URL (PDF or paper page) by scraping, classifying, and generating."""
    load_dotenv()
    console = Console()
    agent = AnthropicAgent(model=model)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Get the paper text
    console.print(f"📥 Fetching content from: {url}")
    try:
        if url.lower().endswith(".pdf"):
            # Direct PDF URL
            with console.status("Downloading and extracting PDF text..."):
                text = fetch_and_extract(url)

            # Create a basic Article object for a direct PDF
            article = Article(
                title="Unknown Title",  # Will be updated if we can extract it
                authors=["Unknown Author"],
                venue="Unknown Venue",
                pdf_url=url,
                links={"PDF": url},
            )
            console.print("✅ PDF text extracted successfully")
        else:
            # Try to scrape the page for article metadata
            with console.status("Scraping page for article metadata..."):
                scraper = AcroconScraper(url=url)
                articles = scraper.scrape()

            if not articles:
                console.print(
                    "❌ No articles found on the page. Trying to treat as direct PDF link..."
                )
                try:
                    text = fetch_and_extract(url)
                    article = Article(
                        title="Unknown Title",
                        authors=["Unknown Author"],
                        venue="Unknown Venue",
                        pdf_url=url,
                        links={"PDF": url},
                    )
                    console.print("✅ Treated as direct PDF and extracted text")
                except Exception as e:
                    console.print(f"❌ Failed to extract content: {e}")
                    raise typer.Exit(code=1)
            else:
                console.print(f"✅ Found {len(articles)} article(s) on the page")

                # Use the first article found
                article = articles[0]
                console.print(f"📄 Processing: {article.title[:80]}...")

                # Get the paper text
                try:
                    if article.pdf_url:
                        with console.status("Downloading and extracting PDF..."):
                            text = fetch_and_extract(article.pdf_url)
                        console.print("✅ PDF text extracted successfully")
                    else:
                        console.print("❌ No PDF URL found in scraped article")
                        raise typer.Exit(code=1)
                except Exception as e:
                    console.print(f"❌ Failed to extract PDF text: {e}")
                    raise typer.Exit(code=1)

        # Step 2: Classify the paper (unless forced)
        if not force_generate:
            console.print("🔍 Classifying paper...")
            with console.status(
                "Determining if this is a real-world application paper..."
            ):
                classification = classify_paper(text, agent)

            if classification["is_real_world_application"]:
                console.print(f"✅ Real-world application: {classification['reason']}")
            else:
                console.print(
                    f"❌ Not a real-world application: {classification['reason']}"
                )
                console.print("Use --force to generate example anyway.")
                raise typer.Exit(code=1)
        else:
            console.print("⚡ Skipping classification (forced generation)")

        # Step 3: Generate the example
        console.print("🤖 Generating example...")
        with console.status("Creating structured example summary..."):
            result = generate_example(article, text, paper_id=1, agent=agent)

        # Step 4: Save the result
        output_path.write_text(result, encoding="utf-8")
        console.print(f"✅ Example saved to: {output_path}")

        # Extract real metadata from generated content for summary
        generated_metadata = _extract_metadata_from_generated_content(result)

        console.print("\n📊 Summary:")
        title = generated_metadata.get("title", article.title)
        authors = generated_metadata.get("authors", article.authors)
        console.print(f"  • Title: {title}")
        console.print(f"  • Authors: {', '.join(authors)}")
        if article.venue != "Unknown Venue":
            console.print(f"  • Venue: {article.venue}")
        if "date" in generated_metadata:
            console.print(f"  • Date: {generated_metadata['date']}")
        console.print(f"  • Output: {output_path}")

    except Exception as e:
        console.print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


def main() -> None:
    app()
