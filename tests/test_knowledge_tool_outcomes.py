import unittest

from backend.runs.request_context import RunRequestContext
from backend.tools.knowledge import _render_rag_result


class KnowledgeToolOutcomeTests(unittest.TestCase):
    def test_clarification_does_not_publish_candidate_rank_as_answer_citation(self):
        context = RunRequestContext.for_sync(user_id="alice", thread_id="thread-1")
        try:
            rendered = _render_rag_result(
                context,
                {
                    "rag_trace": {
                        "route": "clarify",
                        "hitl_prompt": "请确认版本 [4]",
                        "retrieved_chunks": [],
                    }
                },
            )
            self.assertIn("NEEDS_CLARIFICATION", rendered)
            self.assertEqual(context.take_rag_trace()["rag_trace"]["evidence_chunks"], [])
        finally:
            context.close()

    def _render(self, result: dict) -> str:
        # Tool production inputs follow ADR-0015's versioned chunk contract.
        for doc in result.get("docs", []):
            doc.update(
                chunk_id="v1::guide.md::p1::l3::0",
                document_id="d1",
                document_version_id="v1",
                section_id="p1",
                index_version="index-v1",
                content_hash="a" * 64,
            )
        context = RunRequestContext.for_sync(user_id="alice", thread_id="thread-1")
        try:
            return _render_rag_result(context, result)
        finally:
            context.close()

    def test_partial_docs_expose_stable_coverage_gaps_to_answer_model(self):
        rendered = self._render(
            {
                "docs": [
                    {
                        "filename": "guide.md",
                        "page_number": 2,
                        "text": "covered evidence",
                    }
                ],
                "rag_trace": {
                    "retrieval_status": "partial",
                    "retrieval_outcome": "INSUFFICIENT_EVIDENCE",
                    "coverage_gap_codes": [
                        "VECTOR_STORE_UNAVAILABLE",
                        "unsafe secret detail",
                    ],
                    "coverage_gap_questions": ["unknown sub-question"],
                },
            }
        )

        self.assertTrue(rendered.startswith("PARTIAL_EVIDENCE:"))
        self.assertIn("COVERAGE_GAPS: VECTOR_STORE_UNAVAILABLE", rendered)
        self.assertIn('COVERAGE_GAP_QUESTIONS: ["unknown sub-question"]', rendered)
        self.assertIn("Retrieved Chunks:", rendered)
        self.assertIn("covered evidence", rendered)
        self.assertNotIn("unsafe secret detail", rendered)

    def test_mixed_empty_and_provider_failure_is_insufficient_not_no_knowledge(self):
        rendered = self._render(
            {
                "docs": [],
                "rag_trace": {
                    "retrieval_status": "insufficient_evidence",
                    "retrieval_outcome": "INSUFFICIENT_EVIDENCE",
                    "route": "insufficient_evidence",
                },
            }
        )

        self.assertTrue(rendered.startswith("INSUFFICIENT_EVIDENCE:"))
        self.assertNotIn("NO_KNOWLEDGE", rendered)

    def test_healthy_docs_keep_the_normal_retrieval_contract(self):
        rendered = self._render(
            {
                "docs": [
                    {
                        "filename": "guide.md",
                        "page_number": 1,
                        "text": "complete evidence",
                    }
                ],
                "rag_trace": {
                    "retrieval_status": "answerable",
                    "retrieval_outcome": "ANSWERABLE",
                },
            }
        )

        self.assertTrue(rendered.startswith("Retrieved Chunks:"))
        self.assertNotIn("PARTIAL_EVIDENCE", rendered)


if __name__ == "__main__":
    unittest.main()
