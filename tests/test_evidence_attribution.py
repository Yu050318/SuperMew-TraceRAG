from hashlib import sha256
import pytest

from backend.indexing.excel_provenance import source_anchor
from backend.rag.evidence import audit_trace_citations, evidence_trace, pack_evidence
from backend.schemas.rag import normalize_rag_trace
from backend.rag.checkpoint_runner import _compact_resume_result, _restore_resume_result


def leaf(number, product, *, text=None):
    body = text or f"Sheet：库存；产品标识：{product}；库存：88；单位：台"
    return dict(
        filename="inventory.xlsx",
        text=body,
        chunk_id=f"v1::inventory.xlsx::p0::l3::{number}",
        chunk_level=3,
        document_id="doc",
        document_version_id="v1",
        section_id="p0",
        index_version="index",
        content_hash=sha256(body.encode()).hexdigest(),
        tenant_id="tenant",
        knowledge_base_id="kb",
        acl_tags=["private"],
        sheet_name="库存",
        row_start=number + 2,
        row_end=number + 2,
        source_anchor=source_anchor("库存", number + 2, number + 2),
    )


def parent(*leaves):
    result = {
        **leaves[0],
        "chunk_id": "v1::inventory.xlsx::p0::l2::0",
        "chunk_level": 2,
        "merged_from_children": True,
        "text": "父块包括全部产品的上下文",
        "_citation_leaves": list(leaves),
    }
    for key in ("sheet_name", "row_start", "row_end", "source_anchor"):
        result.pop(key)
    result["matched_leaf_sources"] = [
        {
            key: item[key]
            for key in (
                "chunk_id",
                "sheet_name",
                "row_start",
                "row_end",
                "source_anchor",
            )
        }
        for item in leaves
    ]
    result["matched_leaf_sources_truncated"] = False
    return result


def test_target_leaf_is_numbered_but_parent_context_is_not():
    first, target = leaf(0, "NX-001"), leaf(2, "NX-003")
    packed = pack_evidence(
        [parent(first, target)],
        maximum_characters=3000,
        question="NX-003 的库存是多少？",
    )
    assert [doc["chunk_id"] for doc in packed.documents] == [target["chunk_id"]]
    assert "88；单位：台" in packed.text
    assert "父块包括全部产品的上下文" in packed.text
    assert "[1] inventory.xlsx / 库存 / 第 4 行" in packed.text
    assert len(packed.text) <= 3000


def test_selected_leaf_trace_preserves_parent_retrieval_and_true_identity():
    context = parent(leaf(0, "NX-001"), leaf(2, "NX-003"))
    packed = pack_evidence([context], maximum_characters=3000, question="NX-003 库存？")
    trace = evidence_trace({"retrieved_chunks": [context]}, packed)
    assert trace["retrieved_chunks"][0]["chunk_level"] == 2
    assert trace["evidence_chunks"][0]["chunk_level"] == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "foreign"),
        ("knowledge_base_id", "other-kb"),
        ("document_version_id", "v2"),
        ("acl_tags", ["public"]),
        ("index_version", "other-index"),
        ("section_id", "other-section"),
    ],
)
def test_leaf_cannot_cross_authorized_scope(field, value):
    context = parent(leaf(2, "NX-003"))
    context["_citation_leaves"][0][field] = value
    with pytest.raises(ValueError, match="scope"):
        pack_evidence([context], maximum_characters=3000, question="NX-003 库存？")


@pytest.mark.parametrize(
    "failure", ["no_body", "bad_hash", "truncated_sources", "incomplete_bodies"]
)
def test_unavailable_precise_evidence_explicitly_falls_back(failure):
    context = parent(leaf(2, "NX-003"))
    if failure == "no_body":
        context.pop("_citation_leaves")
    elif failure == "bad_hash":
        context["_citation_leaves"][0]["content_hash"] = "a" * 64
    elif failure == "truncated_sources":
        context["matched_leaf_sources_truncated"] = True
    else:
        context["_citation_leaves_incomplete"] = True
    packed = pack_evidence([context], maximum_characters=3000, question="NX-003 库存？")
    assert packed.documents[0]["chunk_level"] == 2
    assert "row_start" not in packed.documents[0]
    assert packed.fallback_count == 1


def test_comparison_keeps_multiple_products_and_fragment_units():
    first = leaf(0, "NX-001")
    second = leaf(2, "NX-003")
    fragment = leaf(
        3, "NX-003", text="Sheet：库存；产品标识：NX-003；功率：60；单位：W；版本：v2"
    )
    fragment.update(row_start=4, row_end=4, source_anchor=source_anchor("库存", 4, 4))
    context = parent(first, second, fragment, leaf(4, "NX-004"))
    packed = pack_evidence(
        [context], maximum_characters=4000, question="比较NX-001与NX-003的库存和功率"
    )
    assert [doc["chunk_id"] for doc in packed.documents] == [
        first["chunk_id"],
        second["chunk_id"],
        fragment["chunk_id"],
    ]
    assert "60；单位：W；版本：v2" in packed.text
    assert [doc["row_start"] for doc in packed.documents] == [2, 4, 4]


def test_duplicate_identity_versions_and_sheets_are_not_assumed_equivalent():
    current = leaf(2, "NX-003")
    old = leaf(
        3, "NX-003", text="Sheet：旧版；产品标识：NX-003；库存：70；单位：台；版本：v1"
    )
    old.update(sheet_name="旧版", source_anchor=source_anchor("旧版", 5, 5))
    packed = pack_evidence(
        [parent(current, old)], maximum_characters=4000, question="NX-003 库存？"
    )
    assert [doc["sheet_name"] for doc in packed.documents] == ["库存", "旧版"]
    assert "库存：70" in packed.text and "库存：88" in packed.text


def test_unselected_leaf_and_invalid_number_are_not_valid_citations():
    context = parent(leaf(0, "NX-001"), leaf(2, "NX-003"))
    packed = pack_evidence([context], maximum_characters=3000, question="NX-003库存？")
    trace = evidence_trace({"retrieved_chunks": [context]}, packed)
    content, trace = audit_trace_citations("库存88台[1]；非法[2]", trace)
    assert content == "库存88台[1]；非法"
    assert trace["cited_evidence_ids"] == [1] and trace["invalid_citation_count"] == 1
    assert normalize_rag_trace({"query": "legacy"}) == {"query": "legacy"}


def test_budgets_and_numbering_are_stable_and_have_no_external_queries():
    context = parent(leaf(2, "NX-003"), leaf(0, "NX-001"))
    packed = pack_evidence(
        [context, context], maximum_characters=190, question="NX-003和NX-001库存？"
    )
    repeated = pack_evidence(
        [context, context], maximum_characters=190, question="NX-003和NX-001库存？"
    )
    assert packed.documents == repeated.documents and packed.text == repeated.text
    assert packed.characters <= 190 and packed.selection_ms >= 0
    assert len({doc["chunk_id"] for doc in packed.documents}) == len(packed.documents)


def test_foreign_leaf_identity_cannot_be_added_to_trace():
    context = parent(leaf(2, "NX-003"))
    foreign = leaf(8, "NX-009")
    with pytest.raises(ValueError):
        normalize_rag_trace(
            {"retrieved_chunks": [context], "evidence_chunks": [foreign]}
        )


def test_conflicting_bodies_for_same_leaf_identity_are_rejected():
    original = leaf(2, "NX-003")
    changed = leaf(
        2, "NX-003", text="Sheet：库存；产品标识：NX-003；库存：999；单位：台"
    )
    with pytest.raises(ValueError, match="conflicting"):
        pack_evidence(
            [parent(original, changed)],
            maximum_characters=3000,
            question="NX-003库存？",
        )


def test_native_retrieval_retains_leaves_without_extra_provider_queries(monkeypatch):
    from test_rag_retrieval_targets import (
        _utils,
        _target,
        _snapshot,
        Embedding,
        TargetStore,
        RoutedStore,
    )

    utils = _utils(AUTO_MERGE_ENABLED="true")
    hits = [leaf(0, "NX-001"), leaf(2, "NX-003")]
    for hit in hits:
        hit["parent_chunk_id"] = "v1::inventory.xlsx::p0::l2::0"
    context = parent(*hits)
    context.pop("_citation_leaves")
    context.pop("matched_leaf_sources")
    context.pop("matched_leaf_sources_truncated")

    class Parents:
        calls = 0

        def get_documents_by_ids(self, ids):
            self.calls += 1
            assert ids == [context["chunk_id"]]
            return [context]

    store = TargetStore(hybrid=hits)
    parents = Parents()
    utils._embedding_service = Embedding()
    utils._milvus_manager = RoutedStore({"catalog": store})
    utils._parent_chunk_store = parents
    frozen = _snapshot(
        _target(
            "catalog",
            filter_expr='tenant_id == "tenant" and document_version_id in ["v1"]',
        ),
        tenant_id="tenant",
    )
    result = utils.retrieve_documents(
        "NX-003库存？", tenant_id="tenant", retrieval_snapshot=frozen
    )
    packed = pack_evidence(
        result["docs"], maximum_characters=3000, question="NX-003库存？"
    )
    assert packed.documents[0]["chunk_id"] == hits[1]["chunk_id"]
    assert (
        len(store.hybrid_calls) == 1 and store.dense_calls == [] and parents.calls == 1
    )
    assert store.hybrid_calls[0]["filter_expr"] == frozen.targets[0].filter_expr


def test_resume_projection_keeps_bounded_authorized_leaf_bodies():
    context = parent(leaf(0, "NX-001"), leaf(2, "NX-003"))
    state = {
        "tenant_id": "tenant",
        "question": "NX-003库存？",
        "docs": [context],
        "rag_trace": {"retrieved_chunks": [context]},
    }
    restored = _restore_resume_result(_compact_resume_result(state))
    packed = pack_evidence(
        restored["docs"], maximum_characters=3000, question=restored["question"]
    )
    assert packed.documents[0]["document_version_id"] == "v1"
    assert packed.documents[0]["content_hash"] == leaf(2, "NX-003")["content_hash"]
    assert "_citation_leaves" not in str(restored["rag_trace"])
    assert "text" not in restored["rag_trace"]["retrieved_chunks"][0]


def test_same_product_in_separately_authorized_versions_keeps_distinct_units():
    first = leaf(2, "NX-003")
    second = leaf(
        2, "NX-003", text="Sheet：库存；产品标识：NX-003；库存：70；单位：台；版本：1.0"
    )
    second.update(
        document_id="doc-2",
        document_version_id="v2",
        chunk_id="v2::inventory.xlsx::p0::l3::2",
    )
    old_parent = parent(second)
    old_parent["chunk_id"] = "v2::inventory.xlsx::p0::l2::0"
    contexts = [parent(first), old_parent]
    packed = pack_evidence(contexts, maximum_characters=4000, question="NX-003库存？")
    trace = evidence_trace({"retrieved_chunks": contexts}, packed)
    assert [item["document_version_id"] for item in trace["evidence_chunks"]] == [
        "v1",
        "v2",
    ]
    assert "库存：88" in packed.text and "库存：70" in packed.text
