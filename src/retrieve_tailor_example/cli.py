"""CLI for generating example summaries from paper URLs."""

import os
from dotenv import load_dotenv
from typing import Annotated

import typer

from retrieve_tailor_example.agents.anthropic import AnthropicAgent, DEFAULT_MODEL
from rich.console import Console

from retrieve_tailor_example.scrapers.acrocon import AcroconScraper
from retrieve_tailor_example.tasks.generate import (
    generate_from_url as generate_from_url_core,
)

app = typer.Typer(
    name="retrieve-tailor-example",
    help="Generate example summaries for publications from a URL.",
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
    ] = True,
) -> None:
    """Generate an example from a single URL (PDF or paper page) by scraping, classifying, and generating."""
    load_dotenv()

    if os.environ.get("ANTHROPIC_API_KEY", None) is None:
        raise RuntimeError("No ANTHROPIC_API_KEY was set.")

    agent = AnthropicAgent(model=model)
    scraper = AcroconScraper(url=url)

    try:
        generate_from_url_core(
            url=url,
            output_file=output_file,
            agent=agent,
            scraper=scraper,
            force_generate=force_generate,
        )
    except RuntimeError as e:
        console = Console()
        console.print(f"❌ Error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console = Console()
        console.print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


def main() -> None:
    app()
