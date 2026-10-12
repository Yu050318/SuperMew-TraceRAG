from backend.schemas.rag import normalize_rag_trace
import pytest
from pydantic import ValidationError


def excel_chunk():
    return {
        "filename": "specs.xlsx",
        "chunk_id": "v1::specs.xlsx::p0::l3::0",
        "chunk_level": 3,
        "document_id": "d1",
        "document_version_id": "v1",
        "section_id": "sheet:Specs",
        "index_version": "catalog-v1",
        "content_hash": "a" * 64,
        "sheet_name": "Specs",
        "row_start": 2,
        "row_end": 2,
        "source_anchor": "sheet:Specs:row:2",
    }


def test_excel_leaf_source_survives_public_trace_without_private_metadata():
    chunk = {**excel_chunk(), "api_key": "private", "file_path": "C:/private"}
    trace = normalize_rag_trace({"retrieved_chunks": [chunk]})
    assert trace["retrieved_chunks"][0] == excel_chunk()


@pytest.mark.parametrize(
    "update",
    [
        {"row_start": True},
        {"row_start": "2"},
        {"row_end": 1},
        {"source_anchor": "sheet:Specs:row:3"},
        {"row_end": None},
        {"sheet_name": "C:\\private"},
        {"chunk_id": "v1::specs.xlsx::p0::l1::0"},
        {"document_version_id": "v2"},
    ],
)
def test_untrusted_or_conflicting_excel_source_is_rejected(update):
    with pytest.raises(ValidationError):
        normalize_rag_trace({"retrieved_chunks": [{**excel_chunk(), **update}]})


def test_parent_preserves_actual_discontinuous_leaf_rows_with_stable_deduplication():
    leaf = excel_chunk()
    source = {
        key: leaf[key]
        for key in ("chunk_id", "sheet_name", "row_start", "row_end", "source_anchor")
    }
    other = {
        **source,
        "chunk_id": "v1::specs.xlsx::p0::l3::4",
        "row_start": 6,
        "row_end": 6,
        "source_anchor": "sheet:Specs:row:6",
    }
    parent = {
        key: value
        for key, value in leaf.items()
        if key not in ("sheet_name", "row_start", "row_end", "source_anchor")
    }
    parent.update(
        chunk_id="v1::specs.xlsx::p0::l1::0",
        chunk_level=1,
        merged_from_children=True,
        matched_leaf_sources=[other, source, source],
    )
    actual = normalize_rag_trace({"retrieved_chunks": [parent]})["retrieved_chunks"][0]
    assert actual["matched_leaf_sources"] == [source, other]
    assert "row_start" not in actual


def test_evidence_pack_renders_true_row_and_charges_location_to_budget():
    from backend.rag.evidence import pack_evidence

    packed = pack_evidence(
        [{**excel_chunk(), "text": "Power: 120 W"}], maximum_characters=150
    )
    assert "specs.xlsx / Specs / 第 2 行" in packed.text
    assert "Page" not in packed.text
    assert packed.characters == len(packed.text) <= 150


def test_citation_ids_only_resolve_selected_evidence_not_retrieval_candidates():
    from backend.rag.evidence import audit_citations

    result = audit_citations("功率120W[1]，其他[2,99]。代码`[99]`", [excel_chunk()])
    assert result.content == "功率120W[1]，其他。代码`[99]`"
    assert result.cited_ids == (1,)
    assert result.citation_count == 3
    assert result.invalid_count == 2


@pytest.mark.parametrize("ids", [[True], ["1"], [0], [2]])
def test_trace_rejects_coerced_or_out_of_pack_citation_ids(ids):
    with pytest.raises(ValidationError):
        normalize_rag_trace(
            {"evidence_chunks": [excel_chunk()], "cited_evidence_ids": ids}
        )


def test_tool_selection_and_answer_audit_have_the_same_identity():
    from backend.rag.evidence import audit_trace_citations
    from backend.tools.knowledge import _render_rag_result
    from backend.runs.request_context import RunRequestContext

    ctx = RunRequestContext.for_sync(
        user_id="test", thread_id="thread-test", tenant_id="tenant-a"
    )
    try:
        doc = {**excel_chunk(), "text": "Power 120 W", "secret": "private"}
        _render_rag_result(
            ctx, {"docs": [doc], "rag_trace": {"retrieved_chunks": [doc]}}
        )
        trace = ctx.peek_rag_trace()["rag_trace"]
        content, trace = audit_trace_citations("120 W[1] mystery[88]", trace)
        assert content == "120 W[1] mystery"
        assert trace["cited_evidence_ids"] == [1]
        assert trace["invalid_citation_count"] == 1
        assert trace["evidence_chunks"][0]["source_anchor"] == "sheet:Specs:row:2"
        assert "secret" not in trace["evidence_chunks"][0]
    finally:
        ctx.close()


def test_selected_source_cannot_be_rebound_to_another_row_or_version():
    leaf = excel_chunk()
    for change in (
        {"document_version_id": "other", "chunk_id": "other::specs.xlsx::p0::l3::0"},
        {"row_start": 6, "row_end": 6, "source_anchor": "sheet:Specs:row:6"},
    ):
        with pytest.raises(ValidationError):
            normalize_rag_trace(
                {"retrieved_chunks": [leaf], "evidence_chunks": [{**leaf, **change}]}
            )


def test_frozen_version_availability_rejects_revocation_without_rebinding():
    from types import SimpleNamespace
    from backend.documents.retrieval import (
        DocumentRetrievalScope,
        RetrievalSnapshot,
        RetrievalTarget,
    )
    from backend.security.milvus_filters import (
        and_filter,
        eq_filter,
        version_identity_filter,
    )

    target = RetrievalTarget(
        "collection_v1",
        and_filter(
            eq_filter("tenant_id", "tenant-a"),
            version_identity_filter(("v1",)),
            eq_filter("chunk_level", 3),
        ),
        ("v1",),
    )
    frozen = RetrievalSnapshot("tenant-a", "old-index", (target,), 1, 1)
    old = SimpleNamespace(
        id="v1",
        status="superseded",
        index_cleaned_at=None,
        vector_collection="collection_v1",
    )
    current = SimpleNamespace(
        id="v2", status="ready", vector_collection="collection_v2"
    )
    document = SimpleNamespace(id="d1", deleted_at=None, current_version=current)
    cleanup = SimpleNamespace(
        document=document, version=old, job=SimpleNamespace(status="pending")
    )
    catalog = SimpleNamespace(
        load_retrieval_snapshot=lambda **_: SimpleNamespace(documents=[document]),
        list_cleanup_jobs_for_versions=lambda **_: [cleanup],
    )
    scope = DocumentRetrievalScope(catalog=catalog)
    scope.assert_snapshot_available(frozen)
    assert frozen.index_id == "old-index" and frozen.targets[
        0
    ].document_version_ids == ("v1",)
    document.deleted_at = "retired"
    with pytest.raises(ValueError):
        scope.assert_snapshot_available(frozen)
    document.deleted_at = None
    old.index_cleaned_at = "cleaned"
    with pytest.raises(ValueError):
        scope.assert_snapshot_available(frozen)


def test_checkpoint_sources_are_metadata_only_and_snapshot_cannot_change_tenant():
    from backend.documents.retrieval import RetrievalSnapshot, RetrievalTarget
    from backend.security.milvus_filters import (
        and_filter,
        eq_filter,
        version_identity_filter,
    )
    from backend.rag.checkpoint_runner import _compact_hitl_state

    target = RetrievalTarget(
        "collection_v1",
        and_filter(
            eq_filter("tenant_id", "tenant-a"),
            version_identity_filter(("v1",)),
            eq_filter("chunk_level", 3),
        ),
        ("v1",),
    )
    snapshot = RetrievalSnapshot("tenant-a", "index-v1", (target,), 1, 1)
    state = _compact_hitl_state(
        {
            "tenant_id": "tenant-a",
            "retrieval_snapshot": snapshot.to_payload(),
            "docs": [{**excel_chunk(), "text": "private body"}],
            "rag_trace": {
                "initial_retrieved_chunks": [
                    {**excel_chunk(), "text": "private body", "secret": "private"}
                ]
            },
        }
    )
    assert state["rag_trace"]["initial_retrieved_chunks"] == [excel_chunk()]
    assert "private" not in str(state)
    assert (
        RetrievalSnapshot.from_payload(
            state["retrieval_snapshot"], tenant_id="tenant-a"
        )
        == snapshot
    )
    with pytest.raises(ValueError):
        RetrievalSnapshot.from_payload(
            state["retrieval_snapshot"], tenant_id="tenant-b"
        )
    state["retrieval_snapshot"]["targets"][0]["filter_expr"] = "tenant_id != 'tenant-a'"
    with pytest.raises(ValueError):
        RetrievalSnapshot.from_payload(
            state["retrieval_snapshot"], tenant_id="tenant-a"
        )


def test_native_hitl_resume_uses_frozen_snapshot_not_new_catalog(monkeypatch):
    from backend.documents.retrieval import RetrievalSnapshot, RetrievalTarget
    from backend.security.milvus_filters import (
        and_filter,
        eq_filter,
        version_identity_filter,
    )
    from backend.runs.request_context import RunRequestContext
    from test_rag_short_circuit import load_pipeline, FakeStructuredModel, _meta

    target = RetrievalTarget(
        "collection_v1",
        and_filter(
            eq_filter("tenant_id", "tenant-a"),
            version_identity_filter(("v1",)),
            eq_filter("chunk_level", 3),
        ),
        ("v1",),
    )
    snapshot = RetrievalSnapshot("tenant-a", "index-v1", (target,), 1, 1)
    monkeypatch.setattr(
        "backend.documents.retrieval.DocumentRetrievalScope.assert_snapshot_available",
        lambda _, frozen: (
            None if frozen == snapshot else pytest.fail("wrong frozen snapshot")
        ),
    )
    calls = []

    def retrieve(query, top_k=5, **kwargs):
        calls.append(kwargs["retrieval_snapshot"])
        return {"docs": [{**excel_chunk(), "text": "Power 120 W"}], "meta": _meta(1)}

    def resolve(**kwargs):
        assert len(calls) == 0, "resume must not resolve a changed Catalog"
        return snapshot

    pipeline = load_pipeline(
        retrieve_documents=retrieve, resolve_retrieval_snapshot=resolve
    )
    grades = iter(
        [
            {
                "relevance": "strong",
                "answerability": "partial",
                "ambiguity": "missing_slot",
                "route": "clarify",
                "hitl_prompt": "版本？",
            },
            {"relevance": "strong", "answerability": "sufficient", "route": "answer"},
        ]
    )
    pipeline._get_complexity_model = lambda *_: FakeStructuredModel(
        lambda *_: {"complexity": "simple"}
    )
    pipeline._get_grader_model = lambda *_: FakeStructuredModel(lambda *_: next(grades))
    ctx = RunRequestContext.for_sync(
        user_id="test", thread_id="thread-test", tenant_id="tenant-a"
    )
    restored_ctx = RunRequestContext.for_sync(
        user_id="test", thread_id="thread-test", tenant_id="tenant-a"
    )
    try:
        result = pipeline.run_rag_graph(
            "请给出这款设备目前版本完整的额定参数并确认适用条件", ctx
        )
        assert result["retrieval_snapshot"]["index_id"] == "index-v1"
        resumed = pipeline.resume_rag_from_hitl(
            result["hitl_resume_state"], "v1", restored_ctx
        )
        assert calls == [snapshot, snapshot]
        assert (
            resumed["rag_trace"]["retrieved_chunks"][0]["source_anchor"]
            == "sheet:Specs:row:2"
        )
    finally:
        ctx.close()
        restored_ctx.close()
