import unittest
from dataclasses import FrozenInstanceError

from packages.evidence_kernel.domain.evidence import (
    CorroborationStatus,
    ExtractedClaim,
    ReviewDecision,
    ReviewStatus,
    SourceReference,
    SourceStatus,
)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceReference("doc-1", "a" * 64, "100 units delivered", 1)

    def test_quote_is_required(self):
        with self.assertRaises(ValueError):
            SourceReference("doc-1", "a" * 64, "  ")

    def test_invalid_hash_rejected(self):
        with self.assertRaises(ValueError):
            SourceReference("doc-1", "not-a-hash", "quote")

    def test_source_and_corrob_are_independent(self):
        fact = ExtractedClaim("f1", "100 units delivered", self.source,
                              SourceStatus.VERIFIED, CorroborationStatus.CONTRADICTED)
        self.assertEqual(fact.source_status, SourceStatus.VERIFIED)
        self.assertEqual(fact.corroboration, CorroborationStatus.CONTRADICTED)
        with self.assertRaises(FrozenInstanceError):
            fact.statement = "changed"

    def test_human_confirmation_is_separate(self):
        fact = ExtractedClaim("f1", "100 units delivered", self.source)
        decision = ReviewDecision("f1", "reviewer-1", ReviewStatus.CONFIRMED, "Reviewed documents")
        self.assertEqual(fact.source_status, SourceStatus.UNVERIFIED)
        self.assertEqual(decision.disposition, ReviewStatus.CONFIRMED)

    def test_pending_is_not_a_decision(self):
        with self.assertRaises(ValueError):
            ReviewDecision("f1", "r1", ReviewStatus.PENDING, "pending")


if __name__ == "__main__":
    unittest.main()
