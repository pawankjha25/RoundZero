"""
Provider-agnostic LLM interface. Never hard-code one provider - see docs/PRD.md
section 18 and section 22 ("store model/provider/temperature/tool configuration
with every attempt").
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMGateway(ABC):
    @abstractmethod
    def complete_json(
        self,
        *,
        system: str,
        user_message: str,
        max_tokens: int = 1024,
    ) -> str:
        """Return raw text expected to be a single JSON object matching the caller's schema."""
        raise NotImplementedError
