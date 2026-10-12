from scripts.audit_rag_citations import audit_case


def test_correct_row_plus_wrong_row_is_not_an_accurate_parent_citation():
    sources = [
        {
            "chunk_id": f"v1::specs.xlsx::p0::l3::{row - 2}",
            "sheet_name": "Specs",
            "row_start": row,
            "row_end": row,
            "source_anchor": f"sheet:Specs:row:{row}",
        }
        for row in (2, 6)
    ]
    parent = {
        "filename": "specs.xlsx",
        "chunk_id": "v1::specs.xlsx::p0::l1::0",
        "chunk_level": 1,
        "document_id": "d1",
        "document_version_id": "v1",
        "section_id": "sheet:Specs",
        "index_version": "idx",
        "content_hash": "a" * 64,
        "merged_from_children": True,
        "matched_leaf_sources": sources,
        "evidence_selected": True,
        "citation_id": 1,
    }
    leaf_map = {
        source["chunk_id"]: {**source, "filename": "specs.xlsx"} for source in sources
    }
    case = {
        "case_id": "unit_fixture",
        "generated_answer": "120 W[1]",
        "retrieved_identities": [parent],
    }
    result = audit_case(case, {("v1", "specs.xlsx", "Specs", 2)}, leaf_map)
    assert result["row_exact_pass"] is False
    assert result["wrong_rows"] == [("v1", "specs.xlsx", "Specs", 6)]
    assert result["citation_count"] == 1 and result["invalid_citation_count"] == 0
    parent["matched_leaf_sources_truncated"] = True
    result = audit_case(
        case,
        {("v1", "specs.xlsx", "Specs", 2), ("v1", "specs.xlsx", "Specs", 6)},
        leaf_map,
    )
    assert result["row_source_indeterminate"] and not result["row_exact_pass"]


def test_missing_and_unknown_citations_are_not_counted_as_correct_rows():
    result = audit_case(
        {
            "case_id": "unit_fixture",
            "generated_answer": "120 W[99]",
            "retrieved_identities": [],
        },
        {("v1", "specs.xlsx", "Specs", 2)},
        {},
    )
    assert result["invalid_citation_count"] == 1
    assert result["row_exact_pass"] is False


def test_derived_evidence_does_not_inflate_retrieval_coverage_population():
    from tests.test_evidence_attribution import leaf, parent

    target = leaf(2, "NX-003")
    context = parent(target)
    context.update(retrieval_context=True, evidence_selected=False)
    target.update(retrieval_context=False, evidence_selected=True, citation_id=1)
    known = {target["chunk_id"]: target}
    result = audit_case(
        {
            "case_id": "fixture",
            "generated_answer": "88台[1]",
            "retrieved_identities": [context, target],
        },
        {("v1", "inventory.xlsx", "库存", 4)},
        known,
    )
    assert result["excel_retrieved"] == 1 and result["excel_covered"] == 1
    assert result["row_exact_pass"] and result["precise_excel_citations"] == 1
    assert not result["safe_fallback"]
