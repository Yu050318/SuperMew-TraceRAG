from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import re
from time import perf_counter
from typing import Any

from backend.core.settings import AppSettings, get_settings
from backend.schemas.rag import RetrievedChunk, normalize_rag_trace


_SEPARATOR = "\n\n---\n\n"
_TRUNCATION_MARKER = "\n…[evidence truncated by context budget]"


@dataclass(frozen=True)
class EvidencePack:
    """A bounded, citation-stable projection of ranked Evidence."""

    documents: tuple[dict[str, Any], ...]
    text: str
    omitted_count: int
    truncated_count: int
    characters: int
    context_characters: int = 0
    fallback_count: int = 0
    selection_ms: float = 0.0


def citation_leaves(document: Mapping[str, Any]) -> list[dict]:
    """Validate bounded, already-retrieved leaf bodies. Never fetch by an unscoped ID."""
    sources = {
        item["chunk_id"]: item for item in document.get("matched_leaf_sources") or []
    }
    leaves = document.get("_citation_leaves") or []
    if not isinstance(leaves, list) or len(leaves) > 32:
        raise ValueError("citation leaf bodies exceed bound")
    result = []
    hashes = {}
    used = 0
    for leaf in leaves:
        for key in (
            "tenant_id",
            "knowledge_base_id",
            "document_id",
            "document_version_id",
            "index_version",
            "section_id",
            "filename",
            "acl_tags",
        ):
            if key not in document or leaf.get(key) != document[key]:
                raise ValueError("citation leaf crosses retrieval scope")
        source = sources.get(leaf.get("chunk_id"))
        if source is None or any(leaf.get(key) != source[key] for key in source):
            raise ValueError("citation leaf is not a matched source")
        payload = RetrievedChunk.model_validate(
            {key: leaf[key] for key in RetrievedChunk.model_fields if key in leaf}
        ).model_dump(exclude_none=True)
        prior = hashes.setdefault(payload["chunk_id"], payload["content_hash"])
        if prior != payload["content_hash"]:
            raise ValueError("conflicting citation leaf content hashes")
        text = payload.get("text") or ""
        if not text or sha256(text.encode()).hexdigest() != payload["content_hash"]:
            continue  # Explicit parent fallback: body unavailable or corrupted, never invent a leaf.
        used += len(text.encode())
        if used > 16384:
            break
        result.append(
            {
                **payload,
                **{
                    key: leaf[key]
                    for key in ("tenant_id", "knowledge_base_id", "acl_tags")
                },
            }
        )
    return sorted(
        {leaf["chunk_id"]: leaf for leaf in result}.values(),
        key=lambda item: item["chunk_id"],
    )


@dataclass(frozen=True)
class CitationAudit:
    """Identity validity only; this does not establish factual support."""

    content: str
    cited_ids: tuple[int, ...]
    citation_count: int
    invalid_count: int


def audit_citations(
    content: str, documents: Sequence[Mapping[str, Any]]
) -> CitationAudit:
    cited: set[int] = set()
    count = invalid = 0
    # Code and Markdown links are not answer citation markers.
    tokens = re.compile(
        r"```[\s\S]*?```|`[^`\n]*`|\[[^\]\n]*\]\([^\n)]*\)|\[([\d\s,]+)\]"
    )

    def replace(match: re.Match[str]) -> str:
        nonlocal count, invalid
        if match.group(1) is None:
            return match.group(0)
        ids = [int(value) for value in re.findall(r"\d+", match.group(1))]
        count += len(ids)
        valid = [value for value in ids if 1 <= value <= len(documents)]
        invalid += len(ids) - len(valid)
        cited.update(valid)
        return "[" + ",".join(map(str, valid)) + "]" if valid else ""

    rendered = tokens.sub(replace, content)
    return CitationAudit(rendered, tuple(sorted(cited)), count, invalid)


def evidence_trace(trace: Mapping[str, Any], pack: EvidencePack) -> dict[str, Any]:
    """Persist exactly the evidence numbered in this answer prompt."""
    return (
        normalize_rag_trace(
            {
                **trace,
                "evidence_chunks": list(pack.documents),
                "evidence_omitted_count": pack.omitted_count,
                "evidence_truncated_count": pack.truncated_count,
                "cited_evidence_ids": [],
                "citation_count": 0,
                "invalid_citation_count": 0,
            }
        )
        or {}
    )


def audit_trace_citations(content: str, trace: dict | None) -> tuple[str, dict | None]:
    # Legacy traces do not promise a numbered EvidencePack. Never infer one
    # from retrieval rank: its selection/budget may have been different.
    if trace is None or "evidence_chunks" not in trace:
        return content, trace
    audit = audit_citations(content, trace["evidence_chunks"])
    return audit.content, normalize_rag_trace(
        {
            **trace,
            "cited_evidence_ids": list(audit.cited_ids),
            "citation_count": audit.citation_count,
            "invalid_citation_count": audit.invalid_count,
        }
    )


def rag_evidence_character_budget(settings: AppSettings | None = None) -> int:
    effective = settings or get_settings()
    return max(int(effective.rag.max_context_tokens), 1)


def agent_evidence_character_budget(settings: AppSettings | None = None) -> int:
    """Reserve at least half of the Agent input budget for instructions and history."""

    effective = settings or get_settings()
    input_budget = max(int(effective.agent.input_token_budget), 1)
    evidence_budget = max(input_budget // 2, 256)
    return min(rag_evidence_character_budget(effective), evidence_budget)


def grader_evidence_character_budget(settings: AppSettings | None = None) -> int:
    """Use a compact evidence projection for routing and answerability grading."""

    effective = settings or get_settings()
    return max(int(effective.rag.grader_evidence_characters), 1)


def grader_max_document_character_budget(
    settings: AppSettings | None = None,
) -> int:
    effective = settings or get_settings()
    return max(int(effective.rag.grader_max_document_characters), 1)


def _document_parts(
    document: Mapping[str, Any],
    *,
    max_document_characters: int | None,
) -> tuple[dict[str, Any], str, bool]:
    projected = dict(document)
    source = str(document.get("filename") or "Unknown")[:240]
    page = str(document.get("page_number") or "N/A")[:40]
    text = str(document.get("text") or "")
    truncated = False
    location = f"{source} (Page {page})"
    source_fields = (
        "sheet_name",
        "row_start",
        "row_end",
        "source_anchor",
        "matched_leaf_sources",
        "matched_leaf_sources_truncated",
    )
    if any(key in document for key in source_fields):
        chunk = RetrievedChunk.model_validate(
            {
                key: document[key]
                for key in RetrievedChunk.model_fields
                if key in document
            }
        ).model_dump(exclude_none=True)
        projected.update({key: chunk[key] for key in source_fields if key in chunk})
        if chunk.get("sheet_name"):
            start, end = chunk["row_start"], chunk["row_end"]
            rows = str(start) if start == end else f"{start}～{end}"
            location = f"{source} / {chunk['sheet_name']} / 第 {rows} 行"
        elif "matched_leaf_sources" in chunk:
            sheets: dict[str, set[tuple[int, int]]] = {}
            for leaf in chunk["matched_leaf_sources"]:
                sheets.setdefault(leaf["sheet_name"], set()).add(
                    (leaf["row_start"], leaf["row_end"])
                )
            labels = []
            for sheet, rows in sorted(sheets.items()):
                row_text = "、".join(
                    str(a) if a == b else f"{a}～{b}" for a, b in sorted(rows)
                )
                labels.append(f"{sheet} / 命中行：{row_text}")
            location = f"{source} / 父块正文；" + "；".join(labels)
            if chunk.get("matched_leaf_sources_truncated"):
                location += "；部分命中来源未展示"
    if max_document_characters is not None and len(text) > max_document_characters:
        text = text[: max(max_document_characters - len(_TRUNCATION_MARKER), 1)]
        text += _TRUNCATION_MARKER
        projected["text"] = text
        projected["evidence_text_truncated"] = True
        truncated = True
    rendered = f"{location}:\n{text}"
    return projected, rendered, truncated


def pack_evidence(
    documents: Sequence[Mapping[str, Any]],
    *,
    maximum_characters: int,
    max_document_characters: int | None = None,
    question: str | None = None,
) -> EvidencePack:
    """Pack ranked documents without cutting a chunk unless none can fit whole."""

    if question is not None:
        started = perf_counter()
        units = []
        contexts = []
        fallbacks = 0
        for document in documents:
            if not document.get("matched_leaf_sources"):
                units.append(document)
                continue
            leaves = citation_leaves(document)
            # The parser repeats the first-column value on every row fragment.
            # ponytail: exact identity narrows candidates, NOT claim entailment;
            # keep ambiguous versions/fragments until claim-level attribution is available.
            identified = []
            for leaf in leaves:
                match = re.match(r"Sheet：[^；]+；[^：；]+：([^；]+)", leaf["text"])
                if (
                    match
                    and match[1].strip()
                    and re.search(
                        r"(?<![A-Za-z0-9_-])"
                        + re.escape(match[1])
                        + r"(?![A-Za-z0-9_-])",
                        question,
                        re.IGNORECASE,
                    )
                ):
                    identified.append(leaf)
            if (
                document.get("matched_leaf_sources_truncated")
                or document.get("_citation_leaves_incomplete")
                or len(leaves) != len(document.get("matched_leaf_sources") or [])
            ):
                units.append(document)
                fallbacks += 1
                continue
            units.extend(identified or leaves)
            contexts.append(
                "父块上下文（无引用编号；引用必须使用下方独立证据，无法支持的事实请说明）：\n"
                + str(document.get("text") or "")
            )
        # Evidence first; context consumes only remaining budget, never displaces a citation.
        units = list({item["chunk_id"]: item for item in units}.values())
        packed = pack_evidence(
            units[:64],
            maximum_characters=maximum_characters,
            max_document_characters=max_document_characters,
        )
        remaining = max(
            int(maximum_characters) - packed.characters - len(_SEPARATOR), 0
        )
        context = "\n\n".join(contexts)[:remaining]
        text = packed.text + (_SEPARATOR + context if context else "")
        return EvidencePack(
            packed.documents,
            text,
            packed.omitted_count + max(len(units) - 64, 0),
            packed.truncated_count,
            len(text),
            len(context),
            fallbacks,
            (perf_counter() - started) * 1000,
        )
    maximum = max(int(maximum_characters), 1)
    per_document = (
        None
        if max_document_characters is None
        else max(int(max_document_characters), 1)
    )
    selected: list[tuple[dict[str, Any], str]] = []
    used = 0
    omitted = 0
    truncated = 0

    for document in documents:
        if not isinstance(document, Mapping):
            omitted += 1
            continue
        projected, body, was_truncated = _document_parts(
            document,
            max_document_characters=per_document,
        )
        citation = len(selected) + 1
        rendered = f"[{citation}] {body}"
        required = len(rendered) + (len(_SEPARATOR) if selected else 0)
        if used + required > maximum:
            omitted += 1
            continue
        selected.append((projected, rendered))
        used += required
        truncated += int(was_truncated)

    if not selected:
        first = next(
            (item for item in documents if isinstance(item, Mapping)),
            None,
        )
        if first is not None:
            projected, body, _ = _document_parts(
                first,
                max_document_characters=None,
            )
            prefix = "[1] "
            available = max(maximum - len(prefix) - len(_TRUNCATION_MARKER), 1)
            rendered = prefix + body[:available] + _TRUNCATION_MARKER
            original_text = str(first.get("text") or "")
            header_characters = len(body) - len(original_text)
            projected["text"] = original_text[: max(available - header_characters, 0)]
            projected["text"] += _TRUNCATION_MARKER
            projected["evidence_text_truncated"] = True
            selected.append((projected, rendered[:maximum]))
            omitted = max(len(documents) - 1, 0)
            truncated = 1

    text = _SEPARATOR.join(rendered for _, rendered in selected)
    return EvidencePack(
        documents=tuple(document for document, _ in selected),
        text=text,
        omitted_count=omitted,
        truncated_count=truncated,
        characters=len(text),
    )


__all__ = [
    "CitationAudit",
    "audit_citations",
    "audit_trace_citations",
    "evidence_trace",
    "EvidencePack",
    "agent_evidence_character_budget",
    "grader_evidence_character_budget",
    "grader_max_document_character_budget",
    "pack_evidence",
    "rag_evidence_character_budget",
]
