"""FastAPI web application for the retrieve-tailor-example tool."""

import re
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from retrieve_tailor_example.agents.anthropic import AnthropicAgent, DEFAULT_MODEL
from retrieve_tailor_example.document import fetch_and_extract
from retrieve_tailor_example.models import Article
from retrieve_tailor_example.scrapers.acrocon import AcroconScraper
from retrieve_tailor_example.tasks.generate import generate_example


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


load_dotenv()

app = FastAPI(
    title="Retrieve Tailor Example Web Interface",
    description="A web interface for generating structured examples from academic papers",
    version="1.0.0",
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Setup static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main page with the form."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
async def generate_from_url(
    request: Request,
    url: str = Form(..., description="URL of the PDF or paper to process"),
    model: str = Form(DEFAULT_MODEL, description="Model to use for generation"),
):
    """Generate an example from a single URL."""

    try:
        agent = AnthropicAgent(model=model)

        # Step 1: Get the paper text
        if url.lower().endswith(".pdf"):
            # Direct PDF URL
            text = fetch_and_extract(url)

            # Create a basic Article object for a direct PDF
            article = Article(
                title="Unknown Title",  # Will be updated if we can extract it
                authors=["Unknown Author"],
                venue="Unknown Venue",
                pdf_url=url,
                links={"PDF": url},
            )
        else:
            # Try to scrape the page for article metadata
            scraper = AcroconScraper(url=url)
            articles = scraper.scrape()

            if not articles:
                # Try to treat as direct PDF link
                try:
                    text = fetch_and_extract(url)
                    article = Article(
                        title="Unknown Title",
                        authors=["Unknown Author"],
                        venue="Unknown Venue",
                        pdf_url=url,
                        links={"PDF": url},
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400, detail=f"Failed to extract content: {e}"
                    )
            else:
                # Use the first article found
                article = articles[0]

                # Get the paper text
                try:
                    if article.pdf_url:
                        text = fetch_and_extract(article.pdf_url)
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="No PDF URL found in scraped article",
                        )
                except Exception as e:
                    raise HTTPException(
                        status_code=400, detail=f"Failed to extract PDF text: {e}"
                    )

        # Step 2: Generate the example
        result = generate_example(article, text, paper_id=1, agent=agent)

        # Extract metadata from generated content for summary
        generated_metadata = _extract_metadata_from_generated_content(result)

        title = generated_metadata.get("title", article.title)
        authors = generated_metadata.get("authors", article.authors)
        date = generated_metadata.get("date", None)
        venue = article.venue if article.venue != "Unknown Venue" else None

        return JSONResponse(
            content={
                "success": True,
                "generated_content": result,
                "metadata": {
                    "title": title,
                    "authors": authors,
                    "date": date,
                    "venue": venue,
                    "url": url,
                },
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """Serve the about page explaining the tool."""
    return templates.TemplateResponse("about.html", {"request": request})


def main():
    """Entry point for the web application."""
    uvicorn.run(
        "retrieve_tailor_example.web.app:app", host="0.0.0.0", port=1234, reload=True
    )


if __name__ == "__main__":
    main()
