"""Mock transactions API for Exercise 2. Standard library only (Python 3.9+).

Run:      python mock_api.py                (listens on http://127.0.0.1:8000)
Options:  --port 8000   --no-faults   (turn off the random 429/500 errors)

Endpoint:
  GET /v1/transactions?limit=100&updated_since=2026-09-01T00:00:00Z&cursor=<opaque>
  Header required: X-API-Key: test-key

Response: {"data": [...], "next_cursor": "<opaque>" | null, "has_more": true|false}
Notes (read carefully; treat this as the API documentation):
  * Records are returned ordered by (updated_at, id) ascending.
  * updated_since is INCLUSIVE (>=).
  * cursor is opaque; pass it back unchanged to get the next page. If both cursor
    and updated_since are supplied, the cursor takes precedence.
  * limit: default 100, maximum 200.
  * A record's fields can change after you have seen it; when it does, updated_at moves
    forward. Ids are unique per transaction.
  * The API is rate limited and can return 429 (with Retry-After seconds) or 500.
  * Data is served as the provider sends it. Do not assume it is perfectly clean.

Interviewer control (not part of the API contract):
  POST /admin/advance   simulates new activity: some existing records are updated
                        and new records appear.
"""
import argparse, base64, json, random, threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

API_KEY = "test-key"
BASE = datetime(2026, 9, 1, tzinfo=timezone.utc)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
LOCK = threading.Lock()
STATE = {"requests": 0, "data_responses": 0, "faults": True}

def build():
    rnd = random.Random(42)
    recs = {}
    for i in range(1, 1001):
        ts = BASE + timedelta(minutes=(i // 10) * 7)   # groups of records share a timestamp
        recs[f"TX{i:06d}"] = {
            "id": f"TX{i:06d}", "player_id": f"P{rnd.randint(1, 120):04d}",
            "type": rnd.choice(["deposit", "withdrawal", "bet", "win"]),
            "amount": round(rnd.uniform(5, 2000), 2), "currency": "NAD",
            "status": rnd.choice(["completed", "completed", "completed", "pending", "failed"]),
            "updated_at": iso(ts)}
    recs["TX000500"]["amount"] = "250.00"      # provider sometimes sends numbers as strings
    recs["TX000777"]["player_id"] = None       # and sometimes omits values
    return recs
RECORDS = build()

def advance():
    rnd = random.Random(7)
    later = BASE + timedelta(days=3)
    ids = rnd.sample([f"TX{i:06d}" for i in range(1, 901)], 40)
    for n, rid in enumerate(ids):
        RECORDS[rid]["status"] = rnd.choice(["completed", "failed", "reversed"])
        RECORDS[rid]["updated_at"] = iso(later + timedelta(minutes=n // 4))
    for j in range(1001, 1026):
        RECORDS[f"TX{j:06d}"] = {"id": f"TX{j:06d}", "player_id": f"P{rnd.randint(1, 120):04d}",
            "type": rnd.choice(["deposit", "bet", "win"]), "amount": round(rnd.uniform(5, 2000), 2),
            "currency": "NAD", "status": "completed", "updated_at": iso(later + timedelta(minutes=12 + j % 5))}

enc = lambda t: base64.urlsafe_b64encode(json.dumps(t).encode()).decode()
dec = lambda s: tuple(json.loads(base64.urlsafe_b64decode(s.encode())))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, headers=None):
        raw = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        if urlparse(self.path).path == "/admin/advance":
            with LOCK: advance()
            return self.send(200, {"ok": True, "total_records": len(RECORDS)})
        self.send(404, {"error": "not found"})
    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/v1/transactions": return self.send(404, {"error": "not found"})
        if self.headers.get("X-API-Key") != API_KEY: return self.send(401, {"error": "invalid api key"})
        with LOCK:
            STATE["requests"] += 1; n = STATE["requests"]
            if STATE["faults"] and n % 9 == 0: return self.send(429, {"error": "rate limited"}, {"Retry-After": "1"})
            if STATE["faults"] and n % 14 == 0: return self.send(500, {"error": "internal error"})
            q = parse_qs(u.query)
            try: limit = min(int(q.get("limit", ["100"])[0]), 200)
            except ValueError: return self.send(400, {"error": "bad limit"})
            rows = sorted(RECORDS.values(), key=lambda r: (r["updated_at"], r["id"]))
            if "cursor" in q:
                try: c = dec(q["cursor"][0])
                except Exception: return self.send(400, {"error": "bad cursor"})
                rows = [r for r in rows if (r["updated_at"], r["id"]) > c]
            elif "updated_since" in q:
                rows = [r for r in rows if r["updated_at"] >= q["updated_since"][0]]
            page = rows[:limit]; more = len(rows) > limit
            data = [dict(r) for r in page]
            STATE["data_responses"] += 1
            if STATE["data_responses"] % 5 == 0 and len(data) > 12:   # occasional repeated record in a response
                data.append(dict(data[10]))
            nxt = enc([page[-1]["updated_at"], page[-1]["id"]]) if page else None
            self.send(200, {"data": data, "next_cursor": nxt if more else None, "has_more": more})

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-faults", action="store_true"); a = ap.parse_args()
    STATE["faults"] = not a.no_faults
    print(f"Mock API on http://127.0.0.1:{a.port}  (faults {'on' if STATE['faults'] else 'off'})")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
