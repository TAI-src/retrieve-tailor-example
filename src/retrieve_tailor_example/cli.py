"""Unified CLI with subcommands: scrape, convert, classify, generate."""

import argparse
import time
from pathlib import Path

from dotenv import load_dotenv

from retrieve_tailor_example.agents.anthropic import AnthropicAgent, DEFAULT_MODEL
from retrieve_tailor_example.document import convert_all_pdfs, download_pdf, slugify
from retrieve_tailor_example.scrapers.acrocon import AcroconScraper
from retrieve_tailor_example.tasks.classify import classify_all_papers
from retrieve_tailor_example.tasks.generate import generate_all_examples


def cmd_scrape(args: argparse.Namespace) -> None:
    """Scrape articles, download PDFs, and save article JSONs."""
    pdf_dir = Path(args.pdf_dir)
    articles_dir = Path(args.articles_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    articles_dir.mkdir(parents=True, exist_ok=True)

    scraper = AcroconScraper(url=args.url)
    print(f"Scraping articles from {args.url}...")
    articles = scraper.scrape()
    print(f"Found {len(articles)} articles.\n")

    downloaded = 0
    for i, article in enumerate(articles, 1):
        if article.pdf_url:
            stem = Path(article.pdf_url.split("/")[-1]).stem
        else:
            stem = slugify(article.title)

        json_path = articles_dir / f"{stem}.json"
        if not json_path.exists():
            article.save(json_path)

        if article.pdf_url:
            print(f"[{i}/{len(articles)}] {article.title[:60]}...")
            path = download_pdf(article.pdf_url, pdf_dir)
            if path is not None:
                downloaded += 1
            if i < len(articles):
                time.sleep(args.delay)

    print(
        f"\nDone: {downloaded} PDFs downloaded, {len(articles)} article JSONs in {articles_dir}/"
    )


def cmd_convert(args: argparse.Namespace) -> None:
    """Convert all PDFs in a directory to .md text files."""
    convert_all_pdfs(input_dir=args.input_dir, output_dir=args.output_dir)


def cmd_classify(args: argparse.Namespace) -> None:
    """Classify papers as real-world application papers or not."""
    load_dotenv()
    agent = AnthropicAgent(model=args.model)
    classify_all_papers(
        md_dir=args.input_dir,
        agent=agent,
        output_path=args.output,
        delay=args.delay,
    )


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate example summaries for real-world application papers."""
    load_dotenv()
    agent = AnthropicAgent(model=args.model)
    generate_all_examples(
        articles_dir=args.articles_dir,
        classifications_path=args.classifications,
        md_dir=args.md_dir,
        output_dir=args.output_dir,
        agent=agent,
        delay=args.delay,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="retrieve-tailor-example",
        description="Scrape, convert, classify, and generate example summaries for publications.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- scrape ---
    p_scrape = subparsers.add_parser(
        "scrape", help="Scrape articles and download PDFs."
    )
    p_scrape.add_argument(
        "--url",
        default="https://www.acrocon.com/~wagner/publications.html",
        help="Publications page URL",
    )
    p_scrape.add_argument(
        "--pdf-dir", default="pdfs", help="Directory to save PDFs (default: pdfs/)"
    )
    p_scrape.add_argument(
        "--articles-dir",
        default="articles",
        help="Directory to save article JSONs (default: articles/)",
    )
    p_scrape.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between downloads in seconds (default: 0.5)",
    )
    p_scrape.set_defaults(func=cmd_scrape)

    # --- convert ---
    p_convert = subparsers.add_parser("convert", help="Convert PDFs to .md text files.")
    p_convert.add_argument(
        "-i", "--input-dir", default="pdfs", help="Directory with PDFs (default: pdfs/)"
    )
    p_convert.add_argument(
        "-o",
        "--output-dir",
        default="pdfs_as_md",
        help="Output directory (default: pdfs_as_md/)",
    )
    p_convert.set_defaults(func=cmd_convert)

    # --- classify ---
    p_classify = subparsers.add_parser(
        "classify", help="Classify papers as real-world application papers."
    )
    p_classify.add_argument(
        "-i",
        "--input-dir",
        default="pdfs_as_md",
        help="Directory with .md files (default: pdfs_as_md/)",
    )
    p_classify.add_argument(
        "-o",
        "--output",
        default="real_world_papers.json",
        help="Output JSON path (default: real_world_papers.json)",
    )
    p_classify.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model to use (default: claude-haiku-4-5-20251001)",
    )
    p_classify.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay between API calls in seconds (default: 0.2)",
    )
    p_classify.set_defaults(func=cmd_classify)

    # --- generate ---
    p_generate = subparsers.add_parser(
        "generate", help="Generate example summaries for real-world papers."
    )
    p_generate.add_argument(
        "-a",
        "--articles-dir",
        default="articles",
        help="Directory with article JSON metadata",
    )
    p_generate.add_argument(
        "-c",
        "--classifications",
        default="ignore_me/real_world_papers.json",
        help="Path to classifications JSON",
    )
    p_generate.add_argument(
        "-m",
        "--md-dir",
        default="pdfs_as_md",
        help="Directory with pre-converted .md paper texts",
    )
    p_generate.add_argument(
        "-o", "--output-dir", default="examples", help="Output directory for examples"
    )
    p_generate.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})",
    )
    p_generate.add_argument(
        "--delay", type=float, default=1.0, help="Delay between API calls in seconds"
    )
    p_generate.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    args.func(args)
