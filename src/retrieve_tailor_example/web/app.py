"""FastAPI web application for the retrieve-tailor-example tool."""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from retrieve_tailor_example.agents.anthropic import AnthropicAgent, DEFAULT_MODEL
from retrieve_tailor_example.scrapers.acrocon import AcroconScraper
from retrieve_tailor_example.tasks.generate import generate_from_url


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
async def generate_from_url_endpoint(
    request: Request,
    url: str = Form(..., description="URL of the PDF or paper to process"),
    model: str = Form(DEFAULT_MODEL, description="Model to use for generation"),
    force_generate: bool = Form(
        True, description="Force generation without classification"
    ),
):
    """Generate an example from a single URL."""
    import tempfile

    try:
        agent = AnthropicAgent(model=model)
        scraper = AcroconScraper(url=url)

        # Create a temporary file to save the result
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as tmp_file:
            temp_path = tmp_file.name

        # Use the shared generate_from_url function
        text, article = generate_from_url(
            url=url,
            output_file=temp_path,
            agent=agent,
            scraper=scraper,
            force_generate=force_generate,
        )

        # Read the generated content
        with open(temp_path, "r", encoding="utf-8") as f:
            result = f.read()

        # Clean up temp file
        import os

        os.unlink(temp_path)

        # Extract metadata from generated content for summary
        from retrieve_tailor_example.tasks.generate import (
            _extract_metadata_from_generated_content,
        )

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
