"""Progressive context construction with token and provenance accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from memory.evidence import EvidenceLedger
from runtime.state import HarnessState


@dataclass(frozen=True)
class ContextBundle:
    text: str
    items: tuple[str, ...]
    estimated_tokens: int
    provenance: tuple[str, ...]


class ContextCompiler:
    def __init__(self, *, token_budget: int = 1800) -> None:
        self.token_budget = token_budget

    @staticmethod
    def _estimate(text: str) -> int:
        return max(1, (len(text) + 3) // 4)

    def compile(
        self,
        *,
        prompt: str,
        state: HarnessState,
        evidence: EvidenceLedger,
        tool_descriptions: Mapping[str, str],
        available_tools: Iterable[str],
        transcript: Iterable[str] = (),
        progressive: bool = True,
        relevant_query: str = "",
    ) -> ContextBundle:
        items: list[str] = [f"TASK: {prompt}", f"STATE_DIGEST: {state.digest()}"]
        provenance: list[str] = ["task", "state_digest"]
        if state.observed_facts:
            items.append("FACTS: " + " | ".join(state.observed_facts[-8:]))
            provenance.append("state.observed_facts")
        if state.verified_outcomes:
            items.append("VERIFIED: " + " | ".join(state.verified_outcomes[-8:]))
            provenance.append("state.verified_outcomes")
        records = evidence.retrieve(relevant_query or prompt, limit=5)
        for record in records:
            items.append(f"EVIDENCE[{record.evidence_id}]: {record.claim} ({record.status})")
            provenance.append(f"evidence:{record.evidence_id}")
        selected = [name for name in available_tools if name in tool_descriptions]
        if progressive:
            selected = selected[:8]
        if selected:
            items.append("TOOLS: " + " | ".join(f"{name}={tool_descriptions[name]}" for name in selected))
            provenance.append("tool_registry")
        history = list(transcript)
        if history:
            if progressive:
                history = history[-4:]
            items.append("TRANSCRIPT: " + " | ".join(history))
            provenance.append("transcript")
        text = "\n".join(items)
        while self._estimate(text) > self.token_budget and len(items) > 2:
            items.pop(-1)
            provenance.pop(-1)
            text = "\n".join(items)
        return ContextBundle(text, tuple(items), self._estimate(text), tuple(provenance))
