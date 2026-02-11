"""Example generation prompts and logic."""

import json
import time
from pathlib import Path

from rich.console import Console

from retrieve_tailor_example.agent import Agent
from retrieve_tailor_example.document import resolve_article_text
from retrieve_tailor_example.models import Article

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
