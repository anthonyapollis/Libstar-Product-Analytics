"""Record handling: validation of unclean data, and new / changed / unchanged classification.
No network or database. Run: python -m unittest discover -s tests   (from exercise2-ingestion/)
"""
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ingest  # noqa: E402

GOOD = {"id": "TX1", "player_id": "P1", "type": "bet", "amount": 10.5, "currency": "NAD",
        "status": "completed", "updated_at": "2026-09-01T00:00:00Z"}


class ValidateTests(unittest.TestCase):
    def test_clean_record(self):
        clean, reason = ingest.validate(GOOD)
        self.assertIsNone(reason)
        self.assertEqual(clean["amount"], Decimal("10.50"))
        self.assertEqual(clean["updated_at"], datetime(2026, 9, 1))

    def test_amount_sent_as_string_is_coerced(self):
        clean, reason = ingest.validate(dict(GOOD, amount="250.00"))
        self.assertIsNone(reason)
        self.assertEqual(clean["amount"], Decimal("250.00"))

    def test_bad_records_are_rejected_with_a_reason(self):
        cases = {
            "missing player_id": dict(GOOD, player_id=None),
            "unparseable amount": dict(GOOD, amount="abc"),
            "negative amount": dict(GOOD, amount=-1),
            "unparseable updated_at": dict(GOOD, updated_at="yesterday"),
            "missing required field": dict(GOOD, status=None),
        }
        for expected, rec in cases.items():
            clean, reason = ingest.validate(rec)
            self.assertIsNone(clean, expected)
            self.assertTrue(reason.startswith(expected), f"{expected!r} -> {reason!r}")


class ClassifyTests(unittest.TestCase):
    class Cur:
        def __init__(self, stored):
            self.stored = stored

        def execute(self, sql, params):
            self.params = params

        def fetchall(self):
            return [(i, self.stored[i]) for i in self.params if i in self.stored]

    def test_new_changed_unchanged_and_older(self):
        t0, t1, t2 = datetime(2026, 9, 1), datetime(2026, 9, 2), datetime(2026, 9, 3)
        cur = self.Cur({"A": t1, "B": t1, "C": t2})
        rows = [{"id": "N", "updated_at": t1},   # not stored -> new
                {"id": "A", "updated_at": t2},   # moved forward -> changed
                {"id": "B", "updated_at": t1},   # same version re-read -> unchanged
                {"id": "C", "updated_at": t0}]   # older than stored -> never written
        new, changed, unchanged = ingest.classify(cur, rows)
        self.assertEqual([r["id"] for r in new], ["N"])
        self.assertEqual([r["id"] for r in changed], ["A"])
        self.assertEqual(sorted(r["id"] for r in unchanged), ["B", "C"])


if __name__ == "__main__":
    unittest.main()
