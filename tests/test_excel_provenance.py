import hashlib

import pytest

from backend.indexing.excel_provenance import matched_leaf_sources, source_anchor
from backend.indexing.milvus_client import _format_retrieval_hit
from backend.providers.rerank import RerankItem, RerankResult
from backend.rag.reranking import RerankStage
import backend.rag.utils as utils


def leaf(index, **updates):
    row = index + 2
    value = {
        "chunk_id": f"v::table.xlsx::p0::l3::{index}",
        "chunk_level": 3,
        "parent_chunk_id": "v::parent",
        "root_chunk_id": "v::root",
        "tenant_id": "t",
        "knowledge_base_id": "k",
        "document_id": "d",
        "document_version_id": "v",
        "index_version": "i",
        "filename": "table.xlsx",
        "file_type": "Excel",
        "section_id": "sheet:s",
        "acl_tags": ["reader"],
        "text": f"型号：NX-{index}；功率：120W",
        "content_hash": hashlib.sha256(str(index).encode()).hexdigest(),
        "score": 1.0,
        "sheet_name": "s",
        "row_start": row,
        "row_end": row,
        "source_anchor": source_anchor("s", row, row),
    }
    return {**value, **updates}


def test_retrieval_output_preserves_and_validates_optional_sources():
    item = leaf(0)
    result = _format_retrieval_hit({"id": 1, "distance": 0.8, "entity": item})
    assert result["source_anchor"] == item["source_anchor"]
    old = {
        k: v
        for k, v in item.items()
        if k not in {"sheet_name", "row_start", "row_end", "source_anchor"}
    }
    assert "source_anchor" not in _format_retrieval_hit(
        {"id": 2, "distance": 0.8, "entity": old}
    )
    with pytest.raises(ValueError):
        _format_retrieval_hit(
            {"id": 1, "distance": 0.8, "entity": {**item, "row_start": "2"}}
        )


def test_duplicate_leaf_from_parallel_queries_stays_a_direct_row_source():
    from backend.schemas.rag import RetrievedChunk
    from backend.rag.evidence import pack_evidence

    first = leaf(0)
    second = leaf(0, score=2.0)
    result = utils.dedupe_documents([first, second])
    assert len(result) == 1
    assert "matched_leaf_sources" not in result[0]
    assert "matched_leaf_sources_truncated" not in result[0]
    assert result[0]["content_hash"] == first["content_hash"]
    assert result[0]["row_start"] == result[0]["row_end"] == 2
    public = {k: v for k, v in result[0].items() if k in RetrievedChunk.model_fields}
    assert RetrievedChunk.model_validate(public).chunk_level == 3
    assert pack_evidence(result, maximum_characters=12000).documents


def test_two_level_parent_merge_preserves_only_hit_leaves(monkeypatch):
    class Executor:
        def call(self, fn, **kwargs):
            return fn()

    parent = {
        k: v
        for k, v in leaf(0).items()
        if k not in {"sheet_name", "row_start", "row_end", "source_anchor"}
    }
    parent.update(
        chunk_id="v::parent", chunk_level=2, parent_chunk_id="v::root", text="rows 2-20"
    )
    root = {**parent, "chunk_id": "v::root", "chunk_level": 1, "parent_chunk_id": ""}

    class Store:
        def get_documents_by_ids(self, ids):
            return [item for item in [parent, root] if item["chunk_id"] in ids]

    monkeypatch.setattr(utils, "_provider_executor", Executor())
    monkeypatch.setattr(utils, "_parent_chunk_store", Store())
    merged, count = utils._merge_to_parent_level(
        [leaf(4), leaf(0), leaf(4)], threshold=2
    )
    assert count == 3 and len(merged) == 1
    assert "row_start" not in merged[0]
    assert [source["row_start"] for source in merged[0]["matched_leaf_sources"]] == [
        2,
        6,
    ]
    final, _ = utils._merge_to_parent_level(merged, threshold=1)
    assert final[0]["chunk_id"] == "v::root"
    assert final[0]["matched_leaf_sources"] == merged[0]["matched_leaf_sources"]


def test_dedupe_keeps_union_of_matched_sources():
    a = {
        **leaf(0),
        "chunk_level": 2,
        "matched_leaf_sources": matched_leaf_sources([leaf(0)])[0],
    }
    b = {**a, "matched_leaf_sources": matched_leaf_sources([leaf(1)])[0]}
    result = utils.dedupe_documents([a, b])
    assert len(result) == 1 and len(result[0]["matched_leaf_sources"]) == 2


def test_sources_are_bounded_and_truncation_is_explicit():
    sources, truncated = matched_leaf_sources([leaf(i) for i in range(80)])
    assert len(sources) == 32 and truncated
    assert matched_leaf_sources([leaf(i) for i in reversed(range(80))]) == (
        sources,
        truncated,
    )


def test_cross_version_sources_rejected():
    value = leaf(0, chunk_level=2)
    value["matched_leaf_sources"] = [
        {
            "chunk_id": "other::leaf",
            "sheet_name": "s",
            "row_start": 2,
            "row_end": 2,
            "source_anchor": source_anchor("s", 2, 2),
        }
    ]
    with pytest.raises(ValueError):
        matched_leaf_sources([value])


def test_rerank_materialization_keeps_internal_sources():
    item = leaf(0)
    stage = RerankStage.__new__(RerankStage)
    result = stage._materialize_result(
        RerankResult(items=(RerankItem(index=0, score=0.9),), attempts=1),
        [item],
        None,
        None,
    )
    assert result[0]["source_anchor"] == item["source_anchor"]


def test_s3_metadata_enters_resume_projection_and_public_trace():
    from backend.rag.pipeline import _copy_jsonable_doc
    from backend.schemas.rag import normalize_rag_trace

    item = leaf(0)
    safe = _copy_jsonable_doc(item)
    assert safe["source_anchor"] == item["source_anchor"]
    assert "matched_leaf_sources" not in safe
    trace = normalize_rag_trace({"retrieved_chunks": [item]})
    assert trace["retrieved_chunks"][0]["source_anchor"] == item["source_anchor"]
