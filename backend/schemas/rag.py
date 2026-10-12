import re
from typing import Annotated, Any, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.indexing.excel_provenance import (
    MAX_MATCHED_SOURCES,
    excel_provenance,
    matched_leaf_sources,
)


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExcelSource(StrictSchema):
    sheet_name: str = Field(
        min_length=1, max_length=31, pattern=r"^[^\x00-\x1f/\\:*?\[\]]+$"
    )
    row_start: int = Field(strict=True, ge=1, le=10000)
    row_end: int = Field(strict=True, ge=1, le=10000)
    source_anchor: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def valid_anchor(self):
        excel_provenance(self.model_dump())
        return self


class MatchedLeafSource(ExcelSource):
    chunk_id: str = Field(min_length=1, max_length=1024)


class RetrievedChunk(StrictSchema):
    filename: str = Field(min_length=1, max_length=240, pattern=r"^[^/\\\x00-\x1f]+$")
    file_type: Optional[str] = None
    page_number: Optional[str | int] = None
    text: Optional[str] = None
    score: Optional[float] = None
    rrf_rank: Optional[int] = None
    rerank_score: Optional[float] = None
    chunk_id: str
    parent_chunk_id: Optional[str] = None
    root_chunk_id: Optional[str] = None
    chunk_level: Optional[int] = None
    chunk_idx: Optional[int] = None
    document_id: str
    document_version_id: str
    section_id: str
    index_version: str
    content_hash: str = Field(
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    merged_from_children: Optional[bool] = None
    merged_child_count: Optional[int] = Field(default=None, ge=0)
    evidence_text_truncated: Optional[bool] = Field(default=None, strict=True)
    sheet_name: Optional[str] = Field(default=None, min_length=1, max_length=31)
    row_start: Optional[int] = Field(default=None, strict=True, ge=1, le=10000)
    row_end: Optional[int] = Field(default=None, strict=True, ge=1, le=10000)
    source_anchor: Optional[str] = Field(default=None, min_length=1, max_length=512)
    matched_leaf_sources: Optional[List[MatchedLeafSource]] = Field(
        default=None, max_length=MAX_MATCHED_SOURCES
    )
    matched_leaf_sources_truncated: Optional[bool] = Field(default=None, strict=True)

    @model_validator(mode="after")
    def valid_excel_sources(self):
        direct = {
            key: getattr(self, key)
            for key in ("sheet_name", "row_start", "row_end", "source_anchor")
            if getattr(self, key) is not None
        }
        if (
            not direct
            and self.matched_leaf_sources is None
            and self.matched_leaf_sources_truncated is None
        ):
            return self
        if not self.filename.lower().endswith(".xlsx") or re.search(
            r"[/\\\x00-\x1f]", self.filename
        ):
            raise ValueError("Excel sources require a safe XLSX filename")
        prefix = f"{self.document_version_id}::{self.filename}::p0::"
        if not re.fullmatch(
            re.escape(prefix) + rf"l{self.chunk_level}::[0-9]+", self.chunk_id
        ):
            raise ValueError(
                "Excel source identity does not match its Document Version/file"
            )
        if direct:
            ExcelSource.model_validate(direct)
            if self.chunk_level != 3 or self.merged_from_children:
                raise ValueError("direct row source must belong to an unmerged L3 leaf")
        if self.matched_leaf_sources is not None:
            if (
                direct
                or self.chunk_level not in (1, 2)
                or not self.merged_from_children
            ):
                raise ValueError("matched sources must belong to a merged parent")
            for source in self.matched_leaf_sources:
                if not re.fullmatch(re.escape(prefix) + r"l3::[0-9]+", source.chunk_id):
                    raise ValueError("matched source has a foreign leaf identity")
            payload = {
                "document_version_id": self.document_version_id,
                "matched_leaf_sources": [
                    s.model_dump() for s in self.matched_leaf_sources
                ],
                "matched_leaf_sources_truncated": self.matched_leaf_sources_truncated
                or False,
            }
            sources, truncated = matched_leaf_sources([payload])
            self.matched_leaf_sources = [
                MatchedLeafSource.model_validate(s) for s in sources
            ]
            self.matched_leaf_sources_truncated = truncated
        elif self.matched_leaf_sources_truncated is not None:
            raise ValueError("source truncation requires a matched source list")
        return self


class RetrievalTargetTrace(StrictSchema):
    collection_name: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,159}$",
    )
    required: bool
    mode: Literal["hybrid", "dense_fallback", "missing_optional"]
    hit_count: int = Field(ge=0)


class RagTraceFields(StrictSchema):
    tool_used: Optional[bool] = None
    tool_name: Optional[str] = None
    query: Optional[str] = None
    rewrite_method: Optional[Literal["step_back", "hyde"]] = None
    rewritten_query: Optional[str] = None
    step_back_question: Optional[str] = None
    hyde_document: Optional[str] = None
    retrieval_stage: Optional[str] = None
    route: Optional[str] = None
    retrieval_status: Optional[str] = None
    retrieval_outcome: Optional[
        Literal["ANSWERABLE", "NO_KNOWLEDGE", "INSUFFICIENT_EVIDENCE"]
    ] = None
    evidence_relevance: Optional[str] = None
    evidence_answerability: Optional[str] = None
    evidence_ambiguity: Optional[str] = None
    evidence_confidence: Optional[float] = None
    evidence_reason: Optional[str] = None
    grader_evidence_characters: Optional[int] = Field(default=None, ge=0)
    grader_evidence_omitted_count: Optional[int] = Field(default=None, ge=0)
    grader_evidence_truncated_count: Optional[int] = Field(default=None, ge=0)
    missing_slots: Optional[List[str]] = None
    hitl_prompt: Optional[str] = None
    hitl_options: Optional[List[str]] = None
    hitl_resumed: Optional[bool] = None
    hitl_answer: Optional[str] = None
    hitl_resume_strategy: Optional[str] = None
    hitl_resume_from_status: Optional[str] = None
    hitl_resume_from_route: Optional[str] = None
    hitl_targeted_retrieved_chunks: Optional[List[RetrievedChunk]] = None
    rerank_enabled: Optional[bool] = None
    rerank_applied: Optional[bool] = None
    rerank_model: Optional[str] = None
    rerank_error_code: Optional[str] = None
    rerank_retryable: Optional[bool] = None
    rerank_attempts: Optional[int] = None
    rerank_fallback_applied: Optional[bool] = None
    rerank_timeout_seconds: Optional[float] = None
    rerank_min_score: Optional[float] = None
    rerank_threshold_applied: Optional[bool] = None
    rerank_skip_reason: Optional[str] = None
    rerank_candidate_count: Optional[int] = None
    rerank_candidate_limit: Optional[int] = None
    rerank_candidate_limit_applied: Optional[bool] = None
    rerank_payload_characters: Optional[int] = None
    rerank_document_character_limit: Optional[int] = None
    rerank_total_character_limit: Optional[int] = None
    rerank_truncated_document_count: Optional[int] = None
    post_rerank_count: Optional[int] = None
    post_threshold_count: Optional[int] = None
    retrieval_empty: Optional[bool] = None
    retrieval_degraded_code: Optional[str] = None
    provider_error_code: Optional[str] = None
    provider_error_stage: Optional[str] = None
    coverage_gap_codes: Optional[List[str]] = None
    coverage_gap_questions: Optional[List[str]] = None
    retrieval_mode: Optional[str] = None
    retrieval_pipeline: Optional[str] = None
    candidate_k: Optional[int] = None
    candidate_k_source: Optional[str] = None
    candidate_k_config_error: Optional[str] = None
    retrieval_candidate_multiplier: Optional[int] = None
    retrieval_top_k: Optional[int] = None
    recall_count: Optional[int] = None
    deduplicated_recall_count: Optional[int] = None
    retrieval_index_id: Optional[str] = Field(
        default=None, min_length=1, max_length=128
    )
    retrieval_target_count: Optional[int] = Field(default=None, ge=0)
    retrieval_required_target_count: Optional[int] = Field(default=None, ge=0)
    retrieval_optional_target_count: Optional[int] = Field(default=None, ge=0)
    retrieval_optional_missing_count: Optional[int] = Field(default=None, ge=0)
    retrieval_target_results: Optional[List[RetrievalTargetTrace]] = None
    post_merge_candidate_count: Optional[int] = None
    candidate_count: Optional[int] = None
    leaf_retrieve_level: Optional[int] = None
    auto_merge_enabled: Optional[bool] = None
    auto_merge_applied: Optional[bool] = None
    auto_merge_threshold: Optional[int] = None
    auto_merge_replaced_chunks: Optional[int] = None
    auto_merge_steps: Optional[int] = None
    retrieved_chunks: Optional[List[RetrievedChunk]] = None
    initial_retrieved_chunks: Optional[List[RetrievedChunk]] = None
    rewrite_retrieved_chunks: Optional[List[RetrievedChunk]] = None
    evidence_chunks: Optional[List[RetrievedChunk]] = Field(default=None, max_length=64)
    evidence_omitted_count: Optional[int] = Field(default=None, ge=0)
    evidence_truncated_count: Optional[int] = Field(default=None, ge=0)
    cited_evidence_ids: Optional[List[Annotated[int, Field(strict=True, ge=1)]]] = (
        Field(default=None, max_length=64)
    )
    citation_count: Optional[int] = Field(default=None, ge=0)
    invalid_citation_count: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def citations_belong_to_selected_evidence(self):
        if self.evidence_chunks is not None and self.retrieved_chunks is not None:

            def identity(chunk):
                return (
                    chunk.document_id,
                    chunk.document_version_id,
                    chunk.chunk_id,
                    chunk.index_version,
                    chunk.content_hash,
                )

            candidates = {identity(chunk): chunk for chunk in self.retrieved_chunks}
            for chunk in self.evidence_chunks:
                candidate = candidates.get(identity(chunk))
                if candidate is None:
                    # An independent L3 unit may descend from a retrieved parent.
                    # Runtime verifies its authorized body/hash before this wire projection.
                    parents = [
                        parent
                        for parent in self.retrieved_chunks
                        if parent.document_id == chunk.document_id
                        and parent.document_version_id == chunk.document_version_id
                        and parent.index_version == chunk.index_version
                        and parent.filename == chunk.filename
                        and parent.section_id == chunk.section_id
                    ]
                    if (
                        chunk.chunk_level == 3
                        and chunk.sheet_name
                        and any(
                            source.chunk_id == chunk.chunk_id
                            and all(
                                getattr(source, field) == getattr(chunk, field)
                                for field in (
                                    "sheet_name",
                                    "row_start",
                                    "row_end",
                                    "source_anchor",
                                )
                            )
                            for parent in parents
                            for source in parent.matched_leaf_sources or []
                        )
                    ):
                        continue
                    raise ValueError(
                        "selected Evidence must belong to current retrieval"
                    )
                for field in (
                    "sheet_name",
                    "row_start",
                    "row_end",
                    "source_anchor",
                    "matched_leaf_sources",
                    "matched_leaf_sources_truncated",
                ):
                    if getattr(chunk, field) != getattr(candidate, field):
                        raise ValueError("selected Evidence source cannot change")
        if self.cited_evidence_ids is not None:
            if self.evidence_chunks is None or any(
                type(i) is not int or not 1 <= i <= len(self.evidence_chunks)
                for i in self.cited_evidence_ids
            ):
                raise ValueError("citation must refer to selected Evidence")
            self.cited_evidence_ids = sorted(set(self.cited_evidence_ids))
        return self

    # 复杂度路由新增字段
    complexity: Optional[str] = None
    complexity_reason: Optional[str] = None
    sub_questions: Optional[List[str]] = None
    sub_agent_count: Optional[int] = None
    synthesis_merged_count: Optional[int] = None


class RagSubTrace(RagTraceFields):
    pass


class RagTrace(RagTraceFields):
    sub_traces: Optional[List[RagSubTrace]] = None


class HitlResumeState(StrictSchema):
    question: str = Field(min_length=1)
    route: Literal["clarify", "scope_select"]
    retrieval_status: Literal["needs_clarification", "needs_scope_selection"]
    rewrite_count: int = Field(default=0, ge=0)
    complexity: Optional[Literal["simple", "complex"]] = None
    complexity_reason: Optional[str] = None
    sub_questions: List[str] = Field(default_factory=list, max_length=4)
    checkpoint_thread_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    interrupt_id: Optional[str] = None


class PendingSkillPin(StrictSchema):
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    version: str = Field(min_length=1, max_length=64)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1, max_length=32)


class PendingHitlState(StrictSchema):
    id: str = Field(min_length=1)
    original_question: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    options: List[str] = Field(default_factory=list)
    route: Literal["clarify", "scope_select"]
    retrieval_status: Literal["needs_clarification", "needs_scope_selection"]
    answers: List[str] = Field(default_factory=list)
    resume_state: HitlResumeState
    skill_pin: Optional[PendingSkillPin] = None
    created_at: str


def _normalize_chunks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    fields = RetrievedChunk.model_fields
    normalized: list[dict] = []
    for item in value:
        if not isinstance(item, dict) or not item.get("filename"):
            continue
        chunk = {key: item[key] for key in fields if key in item}
        content_hash = chunk.get("content_hash")
        if content_hash is not None and (
            not isinstance(content_hash, str)
            or re.fullmatch(r"[0-9a-fA-F]{64}", content_hash) is None
        ):
            if chunk.get("document_version_id"):
                # Versioned artifacts promise manifest identity. Corruption must
                # fail closed instead of being persisted as an ambiguous trace.
                RetrievedChunk.model_validate(chunk)
            chunk.pop("content_hash", None)
        normalized.append(
            RetrievedChunk.model_validate(chunk).model_dump(exclude_none=True)
        )
    return normalized


def _normalize_retrieval_targets(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    fields = RetrievalTargetTrace.model_fields
    return [
        RetrievalTargetTrace.model_validate(
            {key: item[key] for key in fields if key in item}
        ).model_dump()
        for item in value
        if isinstance(item, dict)
    ]


def _normalize_trace_fields(
    trace: dict[str, Any], fields: Mapping[str, Any]
) -> dict[str, Any]:
    normalized = {key: trace[key] for key in fields if key in trace}
    for key in (
        "retrieved_chunks",
        "initial_retrieved_chunks",
        "rewrite_retrieved_chunks",
        "hitl_targeted_retrieved_chunks",
        "evidence_chunks",
    ):
        if key in normalized:
            normalized[key] = _normalize_chunks(normalized[key])
    if "retrieval_target_results" in normalized:
        normalized["retrieval_target_results"] = _normalize_retrieval_targets(
            normalized["retrieval_target_results"]
        )
    return normalized


def normalize_rag_sub_trace(trace: dict | None) -> Optional[dict]:
    if not isinstance(trace, dict) or not trace:
        return None
    normalized = _normalize_trace_fields(trace, RagSubTrace.model_fields)
    return RagSubTrace.model_validate(normalized).model_dump(exclude_none=True)


def normalize_rag_trace(trace: dict | None) -> Optional[dict]:
    if not isinstance(trace, dict) or not trace:
        return None
    normalized = _normalize_trace_fields(trace, RagTrace.model_fields)
    if "sub_traces" in normalized:
        sub_traces = (
            normalized["sub_traces"]
            if isinstance(normalized["sub_traces"], list)
            else []
        )
        normalized["sub_traces"] = [
            item
            for item in (
                normalize_rag_sub_trace(sub_trace)
                for sub_trace in sub_traces
                if isinstance(sub_trace, dict)
            )
            if item is not None
        ]
    return RagTrace.model_validate(normalized).model_dump(exclude_none=True)
