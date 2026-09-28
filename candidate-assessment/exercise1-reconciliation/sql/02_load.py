"""Load the two source CSVs into MySQL exactly as supplied (no cleansing).
Usage: python 02_load.py
"""
import csv
import pymysql

CONN = dict(host="127.0.0.1", user="assess", password="AssessPass123!",
            database="jsb_assessment", autocommit=True)


def load_deposits(cur):
    with open("../internal_deposits.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cur.executemany(
        """INSERT INTO internal_deposits
           (deposit_id, player_id, created_at, amount, currency, method, gateway_ref, status)
           VALUES (%(deposit_id)s, %(player_id)s, %(created_at)s, %(amount)s,
                   %(currency)s, %(method)s, %(gateway_ref)s, %(status)s)""",
        rows,
    )
    return len(rows)


def load_settlement(cur):
    with open("../gateway_settlement.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cur.executemany(
        """INSERT INTO gateway_settlement
           (gateway_txn_id, merchant_ref, settled_at, gross_amount, fee, net_amount, currency, status)
           VALUES (%(gateway_txn_id)s, %(merchant_ref)s, %(settled_at)s, %(gross_amount)s,
                   %(fee)s, %(net_amount)s, %(currency)s, %(status)s)""",
        rows,
    )
    return len(rows)


if __name__ == "__main__":
    conn = pymysql.connect(**CONN)
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        cur.execute("TRUNCATE TABLE internal_deposits")
        cur.execute("TRUNCATE TABLE gateway_settlement")
        n1 = load_deposits(cur)
        n2 = load_settlement(cur)
        cur.execute("SELECT COUNT(*) FROM internal_deposits")
        c1 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gateway_settlement")
        c2 = cur.fetchone()[0]
    print(f"internal_deposits: read {n1} rows from CSV, {c1} rows in table")
    print(f"gateway_settlement: read {n2} rows from CSV, {c2} rows in table")
    conn.close()
