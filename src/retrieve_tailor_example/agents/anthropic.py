"""Anthropic/Claude implementation of the Agent protocol."""

from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


class AnthropicAgent:
    """Agent backed by Anthropic's Claude API."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        self._model = model
        self._client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def ask(
        self,
        text: str,
        question: str,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        user_message = f"<paper>\n{text}\n</paper>\n\n{question}"
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system
            or "You are a helpful research assistant. Answer questions about the provided paper concisely and accurately.",
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
