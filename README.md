# Genearting tailor examples from link to a pdf

> [!WARNING]
> This app was mostly vibe-coded and interacts with LLMs. Make sure not to share private information.

## Prerequisites

### Software
- `uv` (tested on v. 0.9.26).

### An API key

Start by having an `ANTHROPIC_API_KEY` in an `.env` file (or by exporting it).

```sh
ANTHROPIC_API_KEY=sk-...
```

## Using it as a CLI

```bash
uv sync
source .venv/bin/activate
retrieve-tailor-example generate-from-url https://...
```

## Using it as a web service

```bash
uv sync
source .venv/bin/activate
retrieve-tailor-web
```

And then go to `localhost:1234`. 

