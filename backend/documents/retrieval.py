from __future__ import annotations

import re
import json
from dataclasses import asdict
from dataclasses import dataclass

from backend.documents.catalog import (
    DocumentCatalog,
    DocumentRecord,
    DocumentVersionStatus,
)
from backend.security.milvus_filters import (
    and_filter,
    eq_filter,
    version_identity_filter,
)


_COLLECTION_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,159}$")


@dataclass(frozen=True, slots=True)
class RetrievalTarget:
    """一次查询可读取的单个 Milvus collection 与不可变 filter。"""

    collection_name: str
    filter_expr: str
    document_version_ids: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True, slots=True)
class RetrievalSnapshot:
    """由 PostgreSQL current pointer 投影出的查询快照。"""

    tenant_id: str
    index_id: str
    targets: tuple[RetrievalTarget, ...]
    current_document_count: int
    catalog_document_count: int

    def to_payload(self) -> dict:
        payload = asdict(self)
        # Round-trip through the same validation applied at resume.
        self.from_payload(payload, tenant_id=self.tenant_id)
        return payload

    @classmethod
    def from_payload(cls, payload: dict, *, tenant_id: str) -> RetrievalSnapshot:
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 131072:
            raise ValueError("retrieval checkpoint snapshot exceeds 128 KiB")
        if set(payload) != {
            "tenant_id",
            "index_id",
            "targets",
            "current_document_count",
            "catalog_document_count",
        }:
            raise ValueError("invalid retrieval checkpoint fields")
        if (
            payload["tenant_id"] != tenant_id
            or not isinstance(payload["index_id"], str)
            or not 1 <= len(payload["index_id"]) <= 128
        ):
            raise ValueError("retrieval checkpoint scope mismatch")
        for field in ("current_document_count", "catalog_document_count"):
            if type(payload[field]) is not int or not 0 <= payload[field] <= 10000:
                raise ValueError("invalid retrieval checkpoint count")
        entries = payload["targets"]
        if not isinstance(entries, (list, tuple)) or len(entries) > 128:
            raise ValueError("invalid retrieval checkpoint targets")
        targets = []
        for entry in entries:
            if set(entry) != {
                "collection_name",
                "filter_expr",
                "document_version_ids",
                "required",
            }:
                raise ValueError("invalid retrieval checkpoint target fields")
            versions = entry["document_version_ids"]
            if (
                not isinstance(versions, (list, tuple))
                or not 1 <= len(versions) <= 10000
            ):
                raise ValueError("invalid checkpoint versions")
            if any(
                not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", v)
                for v in versions
            ):
                raise ValueError("invalid checkpoint version identity")
            if type(entry["required"]) is not bool:
                raise ValueError("invalid checkpoint target requirement")
            version_ids = tuple(versions)
            expected_filter = and_filter(
                eq_filter("tenant_id", tenant_id),
                version_identity_filter(version_ids),
                eq_filter("chunk_level", 3),
            )
            if entry["filter_expr"] != expected_filter:
                raise ValueError("retrieval checkpoint filter mismatch")
            targets.append(
                RetrievalTarget(
                    _collection_name(entry["collection_name"]),
                    expected_filter,
                    version_ids,
                    entry["required"],
                )
            )
        return cls(
            tenant_id,
            payload["index_id"],
            tuple(targets),
            payload["current_document_count"],
            payload["catalog_document_count"],
        )


def _collection_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not _COLLECTION_RE.fullmatch(normalized):
        raise ValueError("invalid Milvus collection name in document catalog")
    return normalized


class DocumentRetrievalScope:
    """把 Catalog current pointer 转换为 RAG 可消费的深只读 Interface。"""

    def __init__(
        self,
        catalog: DocumentCatalog | None = None,
    ) -> None:
        self._catalog = catalog or DocumentCatalog()

    def assert_snapshot_available(self, snapshot: RetrievalSnapshot) -> None:
        """Check revocation/cleanup without replacing frozen version identities."""
        expected = {
            version: target.collection_name
            for target in snapshot.targets
            for version in target.document_version_ids
        }
        if not expected:
            return
        catalog = self._catalog.load_retrieval_snapshot(tenant_id=snapshot.tenant_id)
        active = {doc.id: doc for doc in catalog.documents if doc.deleted_at is None}
        available = {
            doc.current_version.id: doc.current_version
            for doc in active.values()
            if doc.current_version is not None
            and doc.current_version.status == DocumentVersionStatus.READY
        }
        missing = set(expected) - set(available)
        for cleanup in self._catalog.list_cleanup_jobs_for_versions(
            document_version_ids=missing, tenant_id=snapshot.tenant_id
        ):
            if (
                cleanup.document.id in active
                and cleanup.version.status == DocumentVersionStatus.SUPERSEDED
                and cleanup.version.index_cleaned_at is None
                and cleanup.job.status == "pending"
            ):
                available[cleanup.version.id] = cleanup.version
        if any(
            version not in available
            or available[version].vector_collection != collection
            for version, collection in expected.items()
        ):
            raise ValueError("frozen retrieval versions have been revoked or cleaned")

    @staticmethod
    def _ready_current(document: DocumentRecord):
        version = document.current_version
        if (
            document.deleted_at is not None
            or version is None
            or version.status != DocumentVersionStatus.READY
        ):
            return None
        return version

    def resolve(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str | None = None,
        leaf_chunk_level: int = 3,
    ) -> RetrievalSnapshot:
        tenant = str(tenant_id or "").strip()
        if not tenant:
            raise ValueError("tenant_id must not be empty")
        if leaf_chunk_level < 0:
            raise ValueError("leaf_chunk_level must not be negative")

        catalog_snapshot = self._catalog.load_retrieval_snapshot(
            tenant_id=tenant,
            knowledge_base_id=knowledge_base_id,
        )
        documents = list(catalog_snapshot.documents)
        index_id = catalog_snapshot.index_id

        versioned: dict[str, list[tuple[DocumentRecord, str]]] = {}
        current_document_count = 0

        for document in documents:
            if document.deleted_at is not None:
                continue
            version = self._ready_current(document)
            if version is None:
                continue
            current_document_count += 1
            collection = _collection_name(version.vector_collection)
            versioned.setdefault(collection, []).append((document, version.id))

        targets: list[RetrievalTarget] = []
        for collection, entries in sorted(versioned.items()):
            version_ids = tuple(
                sorted({version_id for _document, version_id in entries})
            )
            targets.append(
                RetrievalTarget(
                    collection_name=collection,
                    filter_expr=and_filter(
                        eq_filter("tenant_id", tenant),
                        version_identity_filter(version_ids),
                        eq_filter("chunk_level", leaf_chunk_level),
                    ),
                    document_version_ids=version_ids,
                    required=True,
                )
            )

        return RetrievalSnapshot(
            tenant_id=tenant,
            index_id=index_id,
            targets=tuple(targets),
            current_document_count=current_document_count,
            catalog_document_count=len(documents),
        )


__all__ = [
    "DocumentRetrievalScope",
    "RetrievalSnapshot",
    "RetrievalTarget",
]
