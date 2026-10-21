import unittest
from decimal import Decimal

from domains.finance.reconciliation import DocumentAmount, Money, compare_invoice_to_po


class FinanceTests(unittest.TestCase):
    def doc(self, id, amount, currency="EUR"):
        return DocumentAmount(id, Money(Decimal(amount), currency), id + "-claim")

    def test_mismatch_creates_review_finding(self):
        finding = compare_invoice_to_po(self.doc("inv", "1200.00"), self.doc("po", "1000.00"))
        self.assertEqual(finding.difference.amount, Decimal("200.00"))
        self.assertEqual(finding.status, "requires_review")
        self.assertEqual(finding.evidence_claim_ids, ("inv-claim", "po-claim"))

    def test_match_has_no_finding(self):
        self.assertIsNone(compare_invoice_to_po(self.doc("inv", "1000.00"), self.doc("po", "1000.00")))

    def test_mixed_currency_rejected(self):
        with self.assertRaises(ValueError):
            compare_invoice_to_po(self.doc("inv", "1000", "USD"), self.doc("po", "1000", "EUR"))

    def test_float_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            Money(1000.0, "EUR")
        with self.assertRaises(ValueError):
            Money(Decimal("NaN"), "EUR")

    def test_negative_difference_preserved(self):
        finding = compare_invoice_to_po(self.doc("inv", "800"), self.doc("po", "1000"))
        self.assertEqual(finding.difference.amount, Decimal("-200"))


if __name__ == "__main__":
    unittest.main()
