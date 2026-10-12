"""Bounded internal Excel sources; not a public Evidence/Checkpoint contract."""

import json
from collections.abc import Mapping, Sequence
from urllib.parse import quote

PROVENANCE_FIELDS = ("sheet_name", "row_start", "row_end", "source_anchor")
MAX_MATCHED_SOURCES = 32
MAX_MATCHED_SOURCE_BYTES = 16384


def source_anchor(sheet: str, start: int, end: int) -> str:
    rows = str(start) if start == end else f"{start}-{end}"
    return f"sheet:{quote(sheet, safe='')}:row:{rows}"


def excel_provenance(value: Mapping) -> dict:
    if not any(key in value for key in PROVENANCE_FIELDS):
        return {}
    sheet = value.get("sheet_name")
    start, end = value.get("row_start"), value.get("row_end")
    if not isinstance(sheet, str) or not sheet or len(sheet) > 31:
        raise ValueError("invalid Excel sheet_name")
    if type(start) is not int or type(end) is not int:
        raise ValueError("Excel row numbers must be integers")
    if not 1 <= start <= end <= 10000:
        raise ValueError("invalid Excel physical row range")
    if value.get("source_anchor") != source_anchor(sheet, start, end):
        raise ValueError("invalid Excel source_anchor")
    return {key: value[key] for key in PROVENANCE_FIELDS}


def matched_leaf_sources(documents: Sequence[dict]) -> tuple[list[dict], bool]:
    sources: dict[str, dict] = {}
    truncated = any(doc.get("matched_leaf_sources_truncated") for doc in documents)
    for doc in documents:
        if "matched_leaf_sources" in doc:
            candidates = doc["matched_leaf_sources"]
            if (
                not isinstance(candidates, list)
                or len(candidates) > MAX_MATCHED_SOURCES
            ):
                raise ValueError("invalid matched leaf sources")
        elif doc.get("chunk_level") == 3 and excel_provenance(doc):
            candidates = [{"chunk_id": doc["chunk_id"], **excel_provenance(doc)}]
        else:
            candidates = []
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise ValueError("invalid matched leaf source")
            chunk_id = candidate.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id or len(chunk_id) > 1024:
                raise ValueError("invalid matched leaf chunk identity")
            version = doc.get("document_version_id")
            if not version or not chunk_id.startswith(f"{version}::"):
                raise ValueError("matched leaf source belongs to another version")
            source = {"chunk_id": chunk_id, **excel_provenance(candidate)}
            if len(source) != 5:
                raise ValueError("matched leaf source missing provenance")
            if chunk_id in sources and sources[chunk_id] != source:
                raise ValueError("conflicting provenance for one leaf")
            sources[chunk_id] = source
    result: list[dict] = []
    for key in sorted(sources):
        candidate = [*result, sources[key]]
        if (
            len(candidate) > MAX_MATCHED_SOURCES
            or len(json.dumps(candidate, ensure_ascii=False).encode("utf-8"))
            > MAX_MATCHED_SOURCE_BYTES
        ):
            truncated = True
            break
        result = candidate
    return result, bool(truncated)
