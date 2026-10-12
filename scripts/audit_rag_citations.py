"""Offline provenance audit of native Evaluation exports; never runs a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.rag.evidence import audit_citations  # noqa: E402
from backend.schemas.rag import RetrievedChunk  # noqa: E402
from backend.evaluation.rag import RagEvalDataset, dataset_fingerprint  # noqa: E402


def source_rows(document: dict, leaf_map: dict) -> tuple[set[tuple], bool]:
    """Only known leaf hits, not all facts/rows contained in a parent body."""
    chunk = RetrievedChunk.model_validate(
        {key: document[key] for key in RetrievedChunk.model_fields if key in document}
    )
    direct = chunk.sheet_name is not None
    sources = (
        [chunk.model_dump(exclude_none=True)]
        if direct
        else [source.model_dump() for source in chunk.matched_leaf_sources or []]
    )
    rows = set()
    complete = bool(sources) and not chunk.matched_leaf_sources_truncated
    for source in sources:
        known = leaf_map.get(source["chunk_id"])
        if (
            known is None
            or any(
                known.get(key) != source.get(key)
                for key in ("sheet_name", "row_start", "row_end", "source_anchor")
            )
            or known.get("filename") != chunk.filename
        ):
            complete = False
            continue
        rows.update(
            (chunk.document_version_id, chunk.filename, source["sheet_name"], row)
            for row in range(source["row_start"], source["row_end"] + 1)
        )
    return rows, complete


def audit_case(case: dict, gold_rows: set[tuple], leaf_map: dict) -> dict[str, Any]:
    identities = list(case.get("retrieved_identities") or [])
    selected = sorted(
        (item for item in identities if item.get("evidence_selected")),
        key=lambda item: item["citation_id"],
    )
    if [item["citation_id"] for item in selected] != list(range(1, len(selected) + 1)):
        raise ValueError("selected Evidence IDs must be contiguous prompt positions")
    audit = audit_citations(str(case.get("generated_answer") or ""), selected)
    excel = [
        item
        for item in identities
        if str(item.get("filename", "")).lower().endswith(".xlsx")
        and item.get("retrieval_context", True)
    ]
    covered = 0
    for item in excel:
        _, complete = source_rows(item, leaf_map)
        covered += int(complete)
    actual_rows: set[tuple] = set()
    indeterminate = False
    cited_sources = []
    for position in audit.cited_ids:
        item = selected[position - 1]
        cited_sources.append(
            {key: value for key, value in item.items() if key != "text"}
        )
        if str(item.get("filename", "")).lower().endswith(".xlsx"):
            rows, complete = source_rows(item, leaf_map)
            actual_rows.update(rows)
            indeterminate |= not complete
    return {
        "case_id": case["case_id"],
        "question": case.get("question"),
        "generated_answer": case.get("generated_answer"),
        "route": (case.get("observation") or {}).get("route"),
        "outcome": (case.get("observation") or {}).get("outcome"),
        "judge": (case.get("observation") or {}).get("judge"),
        "citation_count": audit.citation_count,
        "invalid_citation_count": audit.invalid_count,
        "cited_ids": list(audit.cited_ids),
        "cited_sources": cited_sources,
        "excel_retrieved": len(excel),
        "excel_covered": covered,
        "gold_rows": sorted(gold_rows),
        "actual_cited_rows": sorted(actual_rows),
        "correct_rows": sorted(actual_rows & gold_rows),
        "wrong_rows": sorted(actual_rows - gold_rows),
        "missing_rows": sorted(gold_rows - actual_rows),
        "row_source_indeterminate": indeterminate,
        "row_exact_pass": bool(gold_rows)
        and not indeterminate
        and actual_rows == gold_rows,
        "row_metric_eligible": bool(gold_rows),
        "safe_fallback": any(
            item.get("matched_leaf_sources") for item in cited_sources
        ),
        "precise_excel_citations": sum(
            bool(item.get("sheet_name")) for item in cited_sources
        ),
        "evidence_metrics": next(
            (
                item["evidence_metrics"]
                for item in identities
                if "evidence_metrics" in item
            ),
            None,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "evals/rag/synthetic_enterprise/dataset_dev_v1.json",
    )
    args = parser.parse_args()
    dataset = RagEvalDataset.model_validate_json(
        args.dataset.read_text(encoding="utf8")
    )
    if len(dataset.cases) != 20 or any(
        "dev" not in case.tags for case in dataset.cases
    ):
        raise ValueError("S3 audit permits only the 20-case development split")
    assets = ROOT / "evals/rag/synthetic_enterprise"
    manifest = json.loads((assets / "manifest.json").read_text(encoding="utf8"))
    index = json.loads(
        (args.artifacts / "index-identities.json").read_text(encoding="utf8")
    )
    job = json.loads(
        (args.artifacts / "persistent-job.json").read_text(encoding="utf8")
    )
    profile = json.loads((args.artifacts / "profile.json").read_text(encoding="utf8"))
    if job["status"] != "succeeded" or profile[
        "dataset_fingerprint"
    ] != dataset_fingerprint(dataset):
        raise ValueError("native run/dataset is incomplete or mismatched")
    cases = json.loads(
        (args.artifacts / "persistent-cases.json").read_text(encoding="utf8")
    )["cases"]
    dev_ids = {case.id for case in dataset.cases}
    if len(cases) != 20 or {case["case_id"] for case in cases} != dev_ids:
        raise ValueError("native export does not match development split")
    leaf_map = json.loads(
        (args.artifacts.parent / "s2/leaf-source-identities.json").read_text(
            encoding="utf8"
        )
    )
    versions = {
        doc["canonical_name"]: doc["current_version_id"] for doc in index["documents"]
    }
    names = {
        Path(doc["source_file"]).name: doc["canonical_name"]
        for doc in manifest["documents"]
    }
    ground_truth = {}
    for line in (assets / "ground_truth.jsonl").read_text(encoding="utf8").splitlines():
        truth = json.loads(line)
        if truth["case_id"] not in dev_ids:
            continue
        rows = set()
        for evidence in truth["evidence"]:
            if not evidence["file"].endswith(".xlsx"):
                continue
            filename = names[evidence["file"]]
            sheet, start, end = (
                evidence["sheet"],
                evidence["row_start"],
                evidence["row_end"],
            )
            matching = [
                item
                for item in leaf_map.values()
                if item["filename"] == filename
                and item["sheet_name"] == sheet
                and item["row_start"] == start
                and item["row_end"] == end
            ]
            if not matching:
                raise ValueError("Gold row lacks a verified S2 leaf mapping")
            rows.update(
                (versions[filename], filename, sheet, row)
                for row in range(start, end + 1)
            )
        ground_truth[truth["case_id"]] = rows
    results = [
        audit_case(case, ground_truth[case["case_id"]], leaf_map) for case in cases
    ]
    eligible = [case for case in results if case["row_metric_eligible"]]
    citations = sum(case["citation_count"] for case in results)
    invalid = sum(case["invalid_citation_count"] for case in results)
    excel = sum(case["excel_retrieved"] for case in results)
    covered = sum(case["excel_covered"] for case in results)
    report = {
        "audit_kind": "auxiliary_native_job_export",
        "job_id": job["id"],
        "profile": profile,
        "cases": results,
        "case_count": len(results),
        "provenance_coverage": {
            "numerator": covered,
            "denominator": excel,
            "value": covered / excel if excel else None,
            "population": "final native retrieved XLSX chunks; complete known leaf sources",
        },
        "citation_validity": {
            "numerator": citations - invalid,
            "denominator": citations,
            "value": (citations - invalid) / citations if citations else None,
            "population": "raw native Answer numeric markers; code and links excluded",
        },
        "row_exact_accuracy": {
            "numerator": sum(case["row_exact_pass"] for case in eligible),
            "denominator": len(eligible),
            "value": sum(case["row_exact_pass"] for case in eligible) / len(eligible)
            if eligible
            else None,
            "rule": "exact equality of Gold and cited Excel leaf-row sets; missing citations, extra wrong rows and indeterminate/truncated sources do not pass",
        },
        "citation_recall": {
            "value": None,
            "reason": "Non-Excel Gold section-to-chunk and claim-to-citation attribution are incomplete; not measured",
        },
        "limitations": [
            "Identity/location metrics do not establish claim entailment.",
            "A parent citation identifies hit leaves, not every row in its body.",
            "No frozen cases executed; no Gate or original baseline changed.",
        ],
    }
    correct = sum(len(case["correct_rows"]) for case in eligible)
    predicted = sum(len(case["actual_cited_rows"]) for case in eligible)
    gold = sum(len(case["gold_rows"]) for case in eligible)
    answerable = {
        case.id
        for case in dataset.cases
        if case.expected.outcome and case.expected.outcome.value == "ANSWERABLE"
    }
    report["row_precision"] = {
        "numerator": correct,
        "denominator": predicted,
        "value": correct / predicted if predicted else None,
        "population": "12 Gold-row dev cases; identity/location sets, not claim entailment",
    }
    report["row_recall"] = {
        "numerator": correct,
        "denominator": gold,
        "value": correct / gold if gold else None,
    }
    report["precise_citation_case_coverage"] = {
        "numerator": sum(case["precise_excel_citations"] > 0 for case in eligible),
        "denominator": len(eligible),
    }
    report["overbroad_cases"] = {
        "numerator": sum(bool(case["wrong_rows"]) for case in eligible),
        "denominator": len(eligible),
    }
    report["missing_citation_answerable_cases"] = {
        "case_ids": [
            case["case_id"]
            for case in results
            if case["case_id"] in answerable and not case["cited_ids"]
        ],
        "population_count": len(answerable),
    }
    (args.artifacts / "citation-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "case_count",
                    "provenance_coverage",
                    "citation_validity",
                    "row_exact_accuracy",
                    "citation_recall",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
