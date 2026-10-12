"""Coverage regressions through the existing production graph and Provider seam."""

import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from backend.documents.retrieval import RetrievalSnapshot
from backend.providers import (
    ProviderCallContext,
    ProviderCode,
    ProviderError,
    ProviderOperation,
)

from test_rag_short_circuit import FakeStructuredModel, _doc, _meta, load_pipeline


class CrossDocumentCoverageTests(unittest.TestCase):
    def _pipeline(self):
        return load_pipeline(
            retrieve_documents=lambda *_args, **_kwargs: {"docs": [], "meta": _meta(0)}
        )

    def test_missing_retrieval_evidence_gets_one_rewrite_without_losing_fact(self):
        calls = []

        def retrieve(query, top_k=5, **kwargs):
            calls.append(query)
            body = "设备功率为 15 W" if len(calls) == 1 else "购买日期决定保修期限"
            return {
                "docs": [_doc(body, chunk_id=f"chunk-{len(calls)}")],
                "meta": _meta(1),
            }

        pipeline = load_pipeline(retrieve_documents=retrieve)
        pipeline._get_complexity_model = lambda *_: FakeStructuredModel(
            lambda schema, prompt: {"complexity": "simple", "reason": "single entity"}
        )

        def grade(schema, prompt):
            complete = "购买日期决定保修期限" in prompt and "设备功率为 15 W" in prompt
            return {
                "relevance": "strong",
                "answerability": "sufficient" if complete else "partial",
                "ambiguity": "none",
                "route": "answer" if complete else "clarify",
                "missing_evidence_query": "购买日期适用的保修政策"
                if not complete
                else "",
            }

        pipeline._get_grader_model = lambda *_: FakeStructuredModel(grade)
        state = pipeline._initial_state(
            "购买日期明确的设备功率和保修期分别是多少？", tenant_id="tenant-a"
        )
        result = pipeline.checkpointless_rag_graph.invoke(state)
        self.assertEqual("answerable", result["retrieval_status"])
        self.assertEqual(2, len(calls))
        self.assertEqual("购买日期适用的保修政策", calls[1])
        self.assertEqual(
            {"chunk-1", "chunk-2"}, {d["chunk_id"] for d in result["docs"]}
        )

    def test_missing_purchase_date_does_not_trigger_supplement(self):
        pipeline = load_pipeline(retrieve_documents=lambda *_args, **_kwargs: {})
        grade = pipeline.EvidenceGrade(
            relevance="strong",
            answerability="partial",
            ambiguity="missing_slot",
            route="clarify",
            missing_slots=["购买日期"],
            missing_evidence_query="保修政策",
        )
        self.assertEqual(
            "clarify", pipeline._resolve_route(grade, {"docs": [_doc("政策")]})
        )

    def test_exhausted_rewrite_budget_never_claims_complete_coverage(self):
        pipeline = load_pipeline(retrieve_documents=lambda *_args, **_kwargs: {})
        grade = pipeline.EvidenceGrade(
            relevance="strong",
            answerability="partial",
            ambiguity="none",
            route="clarify",
            missing_evidence_query="缺失政策",
        )
        self.assertEqual(
            "clarify",
            pipeline._resolve_route(
                grade, {"docs": [_doc("参数")], "rewrite_count": 1}
            ),
        )

    def test_existing_complete_evidence_does_not_retrieve_again(self):
        calls = []
        pipeline = load_pipeline(
            retrieve_documents=lambda query, **kw: (
                calls.append(query)
                or {"docs": [_doc("参数及适用政策")], "meta": _meta(1)}
            )
        )
        pipeline._get_complexity_model = lambda *_: FakeStructuredModel(
            lambda *_: {"complexity": "simple"}
        )
        pipeline._get_grader_model = lambda *_: FakeStructuredModel(
            lambda *_: {
                "relevance": "strong",
                "answerability": "sufficient",
                "route": "answer",
            }
        )
        result = pipeline.checkpointless_rag_graph.invoke(
            pipeline._initial_state(
                "设备参数和保修期分别是多少？", tenant_id="tenant-a"
            )
        )
        self.assertEqual("answerable", result["retrieval_status"])
        self.assertEqual(1, len(calls))

    def test_single_fact_ignores_accidental_supplement_suggestion(self):
        pipeline = self._pipeline()
        pipeline._get_grader_model = lambda *_: FakeStructuredModel(
            lambda *_: {
                "relevance": "strong",
                "answerability": "partial",
                "route": "clarify",
                "missing_evidence_query": "政策",
            }
        )
        result = pipeline.grade_documents_node(
            {"question": "功率是多少？", "docs": [_doc("参数")], "rag_trace": {}}
        )
        # Original partial/no-ambiguity route uses the generic rewrite.
        self.assertEqual("rewrite", result["route"])
        self.assertEqual("", result["missing_evidence_query"])

    def test_supplement_does_not_invoke_another_planner(self):
        pipeline = self._pipeline()
        pipeline.rewrite_query_once = Mock(
            side_effect=AssertionError("unexpected model call")
        )
        result = pipeline.rewrite_question_node(
            {
                "question": "参数和政策分别是多少？",
                "missing_evidence_query": "日期适用政策",
                "rewrite_count": 0,
            }
        )
        self.assertEqual("日期适用政策", result["rewritten_query"])
        self.assertEqual(1, result["rewrite_count"])
        pipeline.rewrite_query_once.assert_not_called()

    def test_empty_supplement_preserves_original_evidence_for_regrading(self):
        pipeline = self._pipeline()
        result = pipeline.retrieve_rewritten(
            {
                "tenant_id": "tenant-a",
                "question": "参数和政策分别是多少？",
                "docs": [_doc("参数")],
                "rewrite_method": "step_back",
                "rewritten_query": "缺失政策",
                "missing_evidence_query": "缺失政策",
            }
        )
        self.assertEqual(["chunk-1"], [d["chunk_id"] for d in result["docs"]])

    def test_supplement_provider_failure_is_not_no_knowledge(self):
        for code in (
            ProviderCode.PROVIDER_TIMEOUT,
            ProviderCode.MODEL_RATE_LIMITED,
            ProviderCode.PROVIDER_REQUEST_INVALID,
        ):
            with self.subTest(code=code):

                def fail(*_args, **_kw):
                    raise ProviderError(
                        code=code,
                        context=ProviderCallContext(
                            provider="test", operation=ProviderOperation.VECTOR_SEARCH
                        ),
                    )

                pipeline = load_pipeline(retrieve_documents=fail)
                with self.assertRaises(ProviderError) as raised:
                    pipeline.retrieve_rewritten(
                        {
                            "tenant_id": "tenant-a",
                            "rewrite_method": "step_back",
                            "rewritten_query": "政策",
                            "missing_evidence_query": "政策",
                            "docs": [_doc("参数")],
                        }
                    )
                self.assertEqual(code, raised.exception.code)

    def test_supplement_query_is_schema_bounded(self):
        pipeline = self._pipeline()
        with self.assertRaises(ValidationError):
            pipeline.EvidenceGrade(
                relevance="strong",
                answerability="partial",
                route="rewrite",
                missing_evidence_query="x" * 301,
            )

    def test_date_conditions_are_preserved_in_policy_planning_guidance(self):
        pipeline = self._pipeline()
        prompts = []
        pipeline._get_complexity_model = lambda *_: FakeStructuredModel(
            lambda schema, prompt: (
                prompts.append(prompt)
                or {"complexity": "complex", "sub_questions": ["参数", "日期适用政策"]}
            )
        )
        for date in ("2025-11-01", "2026-02-01"):
            question = f"{date} 购买的设备参数和保修期分别是多少？"
            pipeline.classify_complexity({"question": question})
            self.assertIn(date, prompts[-1])
            self.assertIn("保留购买日期和适用范围", prompts[-1])

    def test_missing_or_inapplicable_policy_remains_partial_after_budget(self):
        pipeline = self._pipeline()
        grade = pipeline.EvidenceGrade(
            relevance="strong",
            answerability="partial",
            route="answer",
            missing_evidence_query="适用政策",
        )
        self.assertEqual(
            "clarify",
            pipeline._resolve_route(
                grade, {"docs": [_doc("其他产品政策")], "rewrite_count": 1}
            ),
        )

    def test_fanout_inherits_exact_snapshot_and_original_requirements(self):
        pipeline = self._pipeline()
        frozen = RetrievalSnapshot("tenant-a", "frozen-index", (), 0, 0).to_payload()
        state = {
            "tenant_id": "tenant-a",
            "question": "参数和政策分别是多少？",
            "sub_questions": ["参数", "政策"],
            "retrieval_snapshot": frozen,
        }
        for send in pipeline._fanout_sub_questions(state):
            self.assertEqual(frozen, send.arg["retrieval_snapshot"])
            self.assertEqual(state["question"], send.arg["original_question"])

    def test_lower_ranked_supplement_stays_visible_to_grader(self):
        pipeline = self._pipeline()
        pipeline._retrieve_for_state = lambda *_: {"docs": [_doc("适用政策", "policy")]}
        original = [_doc(f"参数{i}", f"fact-{i}") for i in range(8)]
        result = pipeline.retrieve_rewritten(
            {
                "question": "参数和政策分别是多少？",
                "docs": original,
                "rewrite_method": "step_back",
                "rewritten_query": "政策",
                "missing_evidence_query": "政策",
            }
        )
        self.assertEqual("policy", result["docs"][1]["chunk_id"])
        self.assertIn("适用政策", pipeline._pack_grader_docs(result["docs"]).text)

    def test_multi_intent_detection_does_not_capture_single_or_version_question(self):
        pipeline = self._pipeline()
        self.assertTrue(
            pipeline._explicit_multi_fact_question("协议和安装要求分别是什么？")
        )
        self.assertFalse(
            pipeline._explicit_multi_fact_question("当前版本和旧版功率有什么区别？")
        )
        self.assertFalse(
            pipeline._explicit_multi_fact_question("不存在的产品功率是多少？")
        )

    def test_rerank_fallback_does_not_override_partial_grade(self):
        pipeline = self._pipeline()
        pipeline._get_grader_model = lambda *_: FakeStructuredModel(
            lambda *_: {
                "relevance": "strong",
                "answerability": "partial",
                "ambiguity": "none",
                "route": "clarify",
                "missing_evidence_query": "缺政策",
            }
        )
        result = pipeline.grade_documents_node(
            {
                "question": "参数和政策分别是多少？",
                "docs": [_doc("参数")],
                "rewrite_count": 1,
                "rag_trace": {"rerank_fallback_applied": True},
            }
        )
        self.assertEqual("INSUFFICIENT_EVIDENCE", result["retrieval_outcome"])


if __name__ == "__main__":
    unittest.main()
