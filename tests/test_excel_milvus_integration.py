"""Explicit real Milvus protocol test; no models or shared collection deletion."""

import os
from dataclasses import replace
from uuid import uuid4

import pytest

from backend.indexing.milvus_client import (
    MilvusSettings,
    MilvusStore,
    RETRIEVAL_OUTPUT_FIELDS,
    _format_retrieval_hit,
)
from backend.indexing.milvus_writer import MilvusWriter
from backend.security.milvus_filters import version_scope_filter
from test_excel_provenance import leaf


@pytest.mark.skipif(
    os.getenv("RUN_S2_MILVUS") != "1",
    reason="explicit isolated Milvus integration opt-in required",
)
def test_real_writer_dense_bm25_hybrid_metadata_and_version_cleanup(monkeypatch):
    from backend.env import load_env

    load_env()
    name = f"s2_provenance_test_{uuid4().hex}"
    store = MilvusStore(replace(MilvusSettings.from_env(), collection_name=name))
    monkeypatch.setenv("DENSE_EMBEDDING_DIM", "16")

    class Embedding:
        def get_embeddings(self, texts):
            return [[1.0] + [0.0] * 15 for _ in texts]

    writer = MilvusWriter(embedding_service=Embedding(), versioned_milvus_manager=store)
    a = leaf(0)
    b = leaf(
        1, tenant_id="other", document_version_id="other-v", chunk_id="other-v::leaf"
    )
    old = {
        k: v
        for k, v in leaf(2, document_version_id="old-v", chunk_id="old-v::leaf").items()
        if k not in {"sheet_name", "row_start", "row_end", "source_anchor"}
    }
    try:
        receipt = writer.write_versioned_documents([a], collection_name=name)
        writer.write_versioned_documents([b], collection_name=name)
        writer.write_versioned_documents([old], collection_name=name)
        assert writer.verify_receipt(receipt).exact
        writer.verify_provenance(receipt, [a])
        expr = version_scope_filter(
            tenant_id="t",
            knowledge_base_id="k",
            document_id="d",
            document_version_ids=["v"],
            index_version="i",
        )
        expr += ' and array_contains(acl_tags, "reader")'
        dense = store.dense_retrieve([1.0] + [0.0] * 15, top_k=5, filter_expr=expr)
        hybrid = store.hybrid_retrieve(
            [1.0] + [0.0] * 15, "功率120W", top_k=5, filter_expr=expr
        )
        with store.session() as client:
            raw = client.search(
                collection_name=name,
                data=["功率120W"],
                anns_field="sparse_embedding",
                search_params={"metric_type": "BM25", "params": {}},
                filter=expr,
                output_fields=RETRIEVAL_OUTPUT_FIELDS,
                limit=5,
                consistency_level="Strong",
            )
        bm25 = [_format_retrieval_hit(hit) for hit in raw[0]]
        for result in (dense, hybrid, bm25):
            assert result and {item["chunk_id"] for item in result} == {a["chunk_id"]}
            assert result[0]["source_anchor"] == a["source_anchor"]
            assert type(result[0]["row_start"]) is int
        legacy = store.dense_retrieve(
            [1.0] + [0.0] * 15, filter_expr='document_version_id == "old-v"'
        )
        assert legacy and "source_anchor" not in legacy[0]
        writer.delete_by_version(receipt)
        assert (
            store.count_by_version(
                tenant_id="t",
                knowledge_base_id="k",
                document_id="d",
                document_version_id="v",
            )
            == 0
        )
        assert (
            store.count_by_version(
                tenant_id="other",
                knowledge_base_id="k",
                document_id="d",
                document_version_id="other-v",
            )
            == 1
        )
    finally:
        assert name.startswith("s2_provenance_test_") and name == store.collection_name
        with store.session() as client:
            if client.has_collection(name):
                client.drop_collection(name)
