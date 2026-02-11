"""Example generation prompts and logic."""

import json
import time
import os
import re
from pathlib import Path

from rich.console import Console
from dotenv import load_dotenv

from retrieve_tailor_example.agent import Agent
from retrieve_tailor_example.scraper import Scraper
from retrieve_tailor_example.document import resolve_article_text, fetch_and_extract
from retrieve_tailor_example.models import Article
from retrieve_tailor_example.tasks.classify import classify_paper

EXAMPLE_FILE = Path(__file__).parents[3] / "example.md"

with EXAMPLE_FILE.open() as fp:
    example_text = fp.read()

TEMPLATE = """\
Here is an example of the format I need:

<format_example>
{example_text}
</format_example>

Now, based on the paper I provided, generate a summary in EXACTLY this format. Rules:
- Use the paper's actual title, authors, and date.
- For the "link" field in the YAML frontmatter, use "_No link available_" if you cannot determine a URL.
- Use id: {paper_id}
- Fill in every section based on the paper's content. If a section cannot be filled from the paper, write "_No response_".
- Do NOT include any text before or after the formatted output.
- The output should start with "---" and end with the author names.
{metadata_block}\
"""

SYSTEM_PROMPT = (
    "You are a research assistant that extracts structured information from "
    "academic papers. You produce output in a specific markdown format. "
    "Output only the requested format, nothing else."
)


def _best_link(article: Article) -> str | None:
    """Pick the best available link from an Article: prefer DOI/publisher over PDF."""
    for label, url in article.links.items():
        if any(
            k in label.lower()
            for k in ("doi", "acm", "springer", "elsevier", "ieee", "online")
        ):
            return url
    for label, url in article.links.items():
        if label.lower() != "pdf":
            return url
    if article.links:
        return next(iter(article.links.values()))
    return None


def _format_metadata_block(article: Article) -> str:
    """Build an extra instruction block with known metadata from an Article."""
    lines = [
        "",
        "I already know the following metadata for this paper \u2014 use it directly:",
        f"- Title: {article.title}",
        f"- Authors: {', '.join(article.authors)}",
        f"- Venue: {article.venue}",
    ]
    link = _best_link(article)
    lines.append(f"- Link: {link}" if link else "- Link: _No link available_")
    return "\n".join(lines)


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


def generate_example(
    article: Article,
    text: str,
    paper_id: int,
    agent: Agent,
) -> str:
    """Generate an example.md-style summary for a single paper.

    Args:
        article: An Article object with metadata.
        text: The paper's full text content.
        paper_id: Numeric ID for the output YAML frontmatter.
        agent: Agent to use for generation.
    """
    metadata_block = _format_metadata_block(article)
    prompt = (
        TEMPLATE.replace("{paper_id}", str(paper_id))
        .replace("{metadata_block}", metadata_block)
        .replace("{example_text}", example_text)
    )

    return agent.ask(
        text,
        prompt,
        system=SYSTEM_PROMPT,
        max_tokens=4096,
    )


console = Console()


def generate_all_examples(
    articles_dir: str | Path,
    classifications_path: str | Path,
    md_dir: str | Path,
    output_dir: str | Path,
    agent: Agent,
    delay: float = 1.0,
) -> list[Path]:
    """Generate example summaries for all real-world application papers."""
    classifications_path = Path(classifications_path)
    articles_dir = Path(articles_dir)
    md_dir_path = Path(md_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    classifications = json.loads(classifications_path.read_text(encoding="utf-8"))
    real_world = [c for c in classifications if c["is_real_world_application"]]

    console.print(f"Found {len(real_world)} real-world application papers.\n")

    generated: list[Path] = []
    for i, entry in enumerate(real_world, 1):
        filename = entry["file"]
        stem = Path(filename).stem
        output_path = output_dir / filename

        if output_path.exists():
            console.print(f"[{i}/{len(real_world)}] Skipping (exists): {filename}")
            generated.append(output_path)
            continue

        article_path = articles_dir / f"{stem}.json"
        if not article_path.exists():
            console.print(f"[{i}/{len(real_world)}] Missing article JSON: {stem}.json")
            continue

        try:
            article = Article.load(article_path)
            text = resolve_article_text(article, md_dir_path)
            with console.status(f"[{i}/{len(real_world)}] Generating: {filename}..."):
                result = generate_example(article, text, paper_id=i, agent=agent)
            output_path.write_text(result, encoding="utf-8")
            console.print(f"[{i}/{len(real_world)}] Generated: {filename}")
            generated.append(output_path)
        except Exception as e:
            console.print(f"[{i}/{len(real_world)}] ERROR: {filename}: {e}")

        if i < len(real_world):
            time.sleep(delay)

    console.print(
        f"\nDone: {len(generated)}/{len(real_world)} examples in {output_dir}/"
    )
    return generated


def generate_from_url(
    url: str,
    output_file: str,
    agent: Agent,
    scraper: Scraper,
    force_generate: bool = True,
) -> tuple[str, Article]:
    """Generate an example from a single URL (PDF or paper page) by scraping, classifying, and generating."""
    load_dotenv()

    if os.environ.get("ANTHROPIC_API_KEY", None) is None:
        raise RuntimeError("No ANTHROPIC_API_KEY was set.")

    console = Console()

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
                    raise e
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
                        raise RuntimeError("No PDF URL found in scraped article")
                except Exception as e:
                    console.print(f"❌ Failed to extract PDF text: {e}")
                    raise e

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
                raise RuntimeError(
                    "The paper provided is not a real-world application."
                )
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
        raise e

    return text, article
