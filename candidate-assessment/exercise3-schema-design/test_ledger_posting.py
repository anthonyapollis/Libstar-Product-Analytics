"""Prove the balance guarantees in ledger_posting.sql and the ledger's CHECK constraints.

Builds ddl.sql + seed.sql + ledger_posting.sql into a throwaway database (default jsb_platform_ledger_test,
dropped at the end), then:
  1. posts a deposit and checks the ledger row and the wallet cache moved together;
  2. replays the same idempotency key: nothing new is posted;
  3. posts a debit bigger than the balance: refused, nothing changes;
  4. reverses a row: an opposite row pointing at the original; the original is untouched;
  5. reverses it again: the first reversal comes back, nothing new is posted;
  6. 20 concurrent postings to one wallet: every balance_before follows the previous balance_after;
  7. direct inserts that break a rule are refused by the CHECK constraints;
  8. after all of it, every wallet's cache still equals the sum of its ledger.
Output goes to the console and evidence/ledger_posting_test.txt.

Database settings: DB_HOST, DB_PORT, DB_SOCKET, DB_USER, DB_PASSWORD (as for the other exercises).
Usage: python test_ledger_posting.py [--database jsb_platform_ledger_test]
"""
import argparse
import os
import re
import threading
from decimal import Decimal
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
LOG, FAILS = [], []


def say(text=""):
    print(text, flush=True)
    LOG.append(text)


def check(ok, what):
    say(f"{'PASS' if ok else 'FAIL'}: {what}")
    if not ok:
        FAILS.append(what)


def connect(database=None):
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
        unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""), database=database, autocommit=True)


def statements(sql):
    """Split a script on ';' (and on '$$' inside DELIMITER blocks), dropping comments."""
    out, delim = [], ";"
    buf = ""
    for line in sql.splitlines():
        if line.strip().upper().startswith("DELIMITER"):
            delim = line.split()[1]
            continue
        if delim == ";":
            line = re.sub(r"--.*$", "", line)
        buf += line + "\n"
        if buf.rstrip().endswith(delim):
            stmt = buf.rstrip()[: -len(delim)].strip()
            if stmt:
                out.append(stmt)
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def run_script(cur, path, db):
    sql = path.read_text(encoding="utf-8").replace("jsb_platform", db)
    for stmt in statements(sql):
        cur.execute(stmt)


def constraint(err):
    m = re.search(r"CONSTRAINT `(\w+)`", str(err))
    return m.group(1) if m else str(err)


def post(cur, key, wallet, ttype, btype, direction, amount, kind=None, rid=None, reason=None):
    cur.execute("CALL post_wallet_txn(%s,%s,%s,%s,%s,%s,%s,%s,%s,'test',NULL,@id)",
                (key, wallet, ttype, btype, direction, amount, kind, rid, reason))
    cur.execute("SELECT @id")
    return cur.fetchone()[0]


def balances(cur, wallet):
    cur.execute("SELECT real_balance, bonus_balance FROM wallets WHERE wallet_id=%s", (wallet,))
    return cur.fetchone()


def ledger_rows(cur):
    cur.execute("SELECT COUNT(*) FROM wallet_transactions")
    return cur.fetchone()[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", default="jsb_platform_ledger_test")
    db = ap.parse_args().database
    assert db != "jsb_platform", "use a throwaway database"

    conn = connect()
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
    for name in ("ddl.sql", "seed.sql", "ledger_posting.sql"):
        run_script(cur, HERE / name, db)
    cur.execute(f"USE `{db}`")
    say(f"database {db}: ddl.sql + seed.sql + ledger_posting.sql loaded; {ledger_rows(cur)} ledger rows")

    say("\n1. A deposit moves the ledger and the cache together")
    real0, _ = balances(cur, 2)
    tid = post(cur, "test:deposit:1", 2, "deposit", "real", "credit", Decimal("100.00"))
    cur.execute("SELECT balance_before, balance_after FROM wallet_transactions WHERE wallet_txn_id=%s", (tid,))
    before, after = cur.fetchone()
    check(before == real0 and after == real0 + 100, f"ledger row {tid}: {before} -> {after}")
    check(balances(cur, 2)[0] == real0 + 100, f"wallet 2 cache is {real0 + 100}")

    say("\n2. Replaying the same event posts nothing")
    n = ledger_rows(cur)
    tid2 = post(cur, "test:deposit:1", 2, "deposit", "real", "credit", Decimal("100.00"))
    check(tid2 == tid and ledger_rows(cur) == n, f"same key returns row {tid2}; still {n} rows")
    check(balances(cur, 2)[0] == real0 + 100, "balance unchanged by the replay")

    say("\n3. A debit larger than the balance is refused")
    n, bal = ledger_rows(cur), balances(cur, 2)
    try:
        post(cur, "test:withdraw:too-much", 2, "withdrawal", "real", "debit", Decimal("99999.00"))
        refused = False
    except pymysql.err.MySQLError as e:
        refused = "insufficient balance" in str(e)
        say(f"refused: {e.args[1]}")
    check(refused and ledger_rows(cur) == n and balances(cur, 2) == bal, "no row posted, balance unchanged")

    say("\n4. A reversal is a new, opposite row; the original is never edited")
    cur.execute("SELECT * FROM wallet_transactions WHERE wallet_txn_id=%s", (tid,))
    original = cur.fetchone()
    cur.execute("CALL reverse_wallet_txn(%s,'Deposit bounced at the bank','test',NULL,@r)", (tid,))
    cur.execute("SELECT @r")
    rid = cur.fetchone()[0]
    cur.execute("SELECT txn_type, direction, amount, reversal_of_wallet_txn_id FROM wallet_transactions "
                "WHERE wallet_txn_id=%s", (rid,))
    check(cur.fetchone() == ("reversal", "debit", Decimal("100.0000"), tid),
          f"row {rid}: reversal, debit 100.00, points at {tid}")
    cur.execute("SELECT * FROM wallet_transactions WHERE wallet_txn_id=%s", (tid,))
    check(cur.fetchone() == original, f"row {tid} is byte-for-byte unchanged")
    check(balances(cur, 2)[0] == real0, f"wallet 2 back to {real0}")

    say("\n5. Reversing twice returns the first reversal")
    n = ledger_rows(cur)
    cur.execute("CALL reverse_wallet_txn(%s,'again','test',NULL,@r)", (tid,))
    cur.execute("SELECT @r")
    check(cur.fetchone()[0] == rid and ledger_rows(cur) == n, f"returns row {rid}; still {n} rows")

    say("\n6. Twenty concurrent postings to one wallet")
    real_start = balances(cur, 1)[0]
    errors = []

    def worker(i):
        try:
            c = connect(db)
            post(c.cursor(), f"test:concurrent:{i}", 1, "deposit", "real", "credit", Decimal("10.00"))
            c.close()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check(not errors, f"all 20 committed ({len(errors)} errors)")
    check(balances(cur, 1)[0] == real_start + 200, f"wallet 1: {real_start} + 20 x 10.00 = {real_start + 200}")
    cur.execute("""SELECT COUNT(*) FROM (
                     SELECT balance_before, LAG(balance_after) OVER (PARTITION BY wallet_id, balance_type
                                                                     ORDER BY wallet_txn_id) AS prev
                     FROM wallet_transactions) x
                   WHERE prev IS NOT NULL AND balance_before <> prev""")
    check(cur.fetchone()[0] == 0, "no break in any wallet's balance_before -> balance_after chain")

    say("\n7. The CHECK constraints refuse rows that break a rule")
    bad = {
        "negative amount": "(1,1,'deposit','real',-5,'credit',0,-5,NULL,NULL,'bad:1')",
        "balance_after that doesn't add up": "(1,1,'deposit','real',5,'credit',0,50,NULL,NULL,'bad:2')",
        "reversal without the row it reverses": "(1,1,'reversal','real',5,'debit',5,0,NULL,'x','bad:3')",
        "manual adjustment without a reason": "(1,1,'manual_adjustment','real',5,'credit',0,5,NULL,NULL,'bad:4')",
    }
    for what, values in bad.items():
        try:
            cur.execute("INSERT INTO wallet_transactions (wallet_id, player_id, txn_type, balance_type, amount, "
                        "direction, balance_before, balance_after, reversal_of_wallet_txn_id, reason, "
                        "idempotency_key, created_at_utc) VALUES " + values[:-1] + ", UTC_TIMESTAMP(6))")
            check(False, f"{what}: accepted")
        except pymysql.err.MySQLError as e:
            check("constraint" in str(e).lower() or e.args[0] in (3819, 4025), f"{what}: refused by {constraint(e)}")
    try:
        cur.execute("INSERT INTO bets (request_id, player_id, product, channel, stake_real_amount, stake_bonus_amount, "
                    "status, placed_at_utc) VALUES ('bad-bet', 3, 'casino', 'app', 0, 5, 'open', UTC_TIMESTAMP(6))")
        check(False, "bonus-funded bet without its grant: accepted")
    except pymysql.err.MySQLError as e:
        check("ck_bets_bonus_funding" in str(e), f"bonus-funded bet without its grant: refused by {constraint(e)}")

    say("\n8. Every wallet's cache equals its ledger")
    cur.execute("""SELECT COUNT(*) FROM wallets w
                   LEFT JOIN (SELECT wallet_id,
                                SUM(IF(balance_type='real',  IF(direction='credit', amount, -amount), 0)) AS r,
                                SUM(IF(balance_type='bonus', IF(direction='credit', amount, -amount), 0)) AS b
                              FROM wallet_transactions GROUP BY wallet_id) l USING (wallet_id)
                   WHERE w.real_balance <> COALESCE(l.r, 0) OR w.bonus_balance <> COALESCE(l.b, 0)""")
    check(cur.fetchone()[0] == 0, "no wallet differs from its ledger")

    cur.execute(f"DROP DATABASE `{db}`")
    say(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED'} (database {db} dropped)")
    (HERE / "evidence").mkdir(exist_ok=True)
    (HERE / "evidence" / "ledger_posting_test.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
