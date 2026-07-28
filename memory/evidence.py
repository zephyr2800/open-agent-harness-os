"""Compact provenance-linked evidence ledger."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from protocol.digest import sha256_digest


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    claim: str
    evidence: tuple[str, ...]
    status: str
    source_trace: str
    created_at: str
    expires: str | None = None

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["evidence"] = list(self.evidence)
        return value


class EvidenceLedger:
    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}

    def add(self, *, claim: str, evidence: Iterable[str], status: str, source_trace: str, expires: str | None = None) -> EvidenceRecord:
        evidence_tuple = tuple(item for item in evidence if item)
        if not claim or not evidence_tuple:
            raise ValueError("claim and evidence are required")
        payload = {"claim": claim, "evidence": evidence_tuple, "source_trace": source_trace}
        record = EvidenceRecord(
            evidence_id=sha256_digest(payload),
            claim=claim,
            evidence=evidence_tuple,
            status=status,
            source_trace=source_trace,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires=expires,
        )
        self._records[record.evidence_id] = record
        return record

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._records.get(evidence_id)

    def retrieve(self, query: str, *, limit: int = 5) -> tuple[EvidenceRecord, ...]:
        terms = {term.lower() for term in query.split() if len(term) > 2}
        scored: list[tuple[int, EvidenceRecord]] = []
        for record in self._records.values():
            haystack = (record.claim + " " + " ".join(record.evidence)).lower()
            score = sum(term in haystack for term in terms)
            if score or not terms:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].created_at, item[1].evidence_id))
        return tuple(record for _, record in scored[:limit])

    def all(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records.values())

    def contains_verified(self, evidence_ids: Iterable[str]) -> bool:
        ids = tuple(evidence_ids)
        return bool(ids) and all(self._records.get(item) is not None and self._records[item].status == "verified" for item in ids)
