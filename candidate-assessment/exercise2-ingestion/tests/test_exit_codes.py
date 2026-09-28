"""Regression for Codex QA-02: a FAILED run must exit non-zero.
No network or database: HTTP and MySQL are replaced by test doubles.
Run: python -m unittest discover -s tests   (from exercise2-ingestion/)
"""
import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ingest  # noqa: E402


class FakeCursor:
    lastrowid = 1
    rowcount = 0
    lock_free = True

    def execute(self, sql, params=None):
        self.last = sql

    def executemany(self, sql, params=None):
        pass

    def fetchone(self):
        if "GET_LOCK" in self.last:
            return (1 if FakeCursor.lock_free else 0,)
        return None           # no checkpoint -> full load

    def fetchall(self):
        return []             # nothing stored yet


class FakeConn:
    def cursor(self):
        return FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def http_error(code, headers=None):
    return urllib.error.HTTPError("http://test", code, "err", headers or {}, io.BytesIO(b"{}"))


def one_page(req, timeout=10):
    body = b'{"data": [{"id": "TX1", "player_id": "P1", "type": "bet", "amount": 10, ' \
           b'"currency": "NAD", "status": "completed", "updated_at": "2026-09-01T00:00:00Z"}], ' \
           b'"next_cursor": null, "has_more": false}'
    resp = mock.MagicMock()
    resp.__enter__.return_value.read.return_value = body
    return resp


class ExitCodeTests(unittest.TestCase):
    def run_main(self, urlopen):
        with mock.patch.object(ingest.pymysql, "connect", return_value=FakeConn()), \
             mock.patch.object(ingest.urllib.request, "urlopen", side_effect=urlopen), \
             mock.patch.object(ingest.time, "sleep"), \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            return ingest.main()

    def test_api_401_exits_non_zero(self):
        def fail(req, timeout=10):
            raise http_error(401)
        self.assertEqual(self.run_main(fail), 1)

    def test_rate_limit_retries_exhausted_exits_non_zero(self):
        def always_429(req, timeout=10):
            raise http_error(429, {"Retry-After": "0"})
        self.assertEqual(self.run_main(always_429), 1)

    def test_server_errors_exhausted_exits_non_zero(self):
        def always_500(req, timeout=10):
            raise http_error(500)
        self.assertEqual(self.run_main(always_500), 1)

    def test_completed_run_exits_zero(self):
        self.assertEqual(self.run_main(one_page), 0)

    def test_second_run_skips_while_lock_held(self):
        FakeCursor.lock_free = False
        try:
            calls = []
            self.assertEqual(self.run_main(lambda req, timeout=10: calls.append(req)), 0)
            self.assertEqual(calls, [], "a skipped run must not call the API")
        finally:
            FakeCursor.lock_free = True


if __name__ == "__main__":
    unittest.main()
