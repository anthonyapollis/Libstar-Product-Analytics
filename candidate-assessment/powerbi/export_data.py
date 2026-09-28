"""Export the dbt models Power BI reads to data/*.csv (then run build_pbip.py to embed them).

Run after `dbt build`. Every file is a straight SELECT from one dbt model, so the report shows
exactly what the tested reporting layer holds.
Connection from env: DB_HOST, DB_PORT, DB_SOCKET, DB_USER, DB_PASSWORD (as for the other scripts).
Usage: python export_data.py
"""
import csv
import os
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
MARTS, STAGING = "jsb_platform_marts", "jsb_platform_staging"

# csv file -> (schema, dbt model, order by)
EXPORTS = {
    "dim_player": (MARTS, "dim_player", "player_id"),
    "dim_player_vip_tier_scd": (MARTS, "dim_player_vip_tier_scd", "player_id, valid_from_utc"),
    "dim_campaign": (MARTS, "dim_campaign", "campaign_id"),
    "dim_date": (MARTS, "dim_date", "date_day"),
    "fact_bet": (MARTS, "fact_bet", "bet_id"),
    "fact_wallet_transaction": (MARTS, "fact_wallet_transaction", "wallet_txn_id"),
    "fact_bonus_transaction": (MARTS, "fact_bonus_transaction", "player_bonus_id"),
    "mart_ngr_by_product_monthly": (MARTS, "mart_ngr_by_product_monthly", "product, month_start"),
    "mart_bonus_cost_pct_of_ngr": (MARTS, "mart_bonus_cost_pct_of_ngr", "campaign_name, month_start"),
    "fct_recon_exceptions": (MARTS, "fct_recon_exceptions", "recon_key"),
    "mart_recon_bridge": (MARTS, "mart_recon_bridge", "step_order"),
    "ingest_runs": (STAGING, "stg_ingest_runs", "run_id"),
    "transactions": (MARTS, "fct_api_transactions", "id"),
}


def main():
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
        unix_socket=os.environ.get("DB_SOCKET") or None, user=os.environ.get("DB_USER", "assess"),
        password=os.environ.get("DB_PASSWORD", "AssessPass123!"))
    for name, (schema, model, order) in EXPORTS.items():
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {schema}.{model} ORDER BY {order}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        with open(HERE / "data" / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(["" if v is None else v for v in r] for r in rows)
        print(f"{name}.csv: {len(rows)} rows from {schema}.{model}")
    conn.close()


if __name__ == "__main__":
    main()
