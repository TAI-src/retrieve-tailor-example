"""Agent protocol — the LLM abstraction layer."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Agent(Protocol):
    def ask(
        self,
        text: str,
        question: str,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> str: ...
