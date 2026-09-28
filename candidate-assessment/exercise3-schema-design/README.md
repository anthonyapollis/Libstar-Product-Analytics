# Exercise 3: database design for players, wallets, bets and bonuses

**Tools:** MariaDB 10.11 (MySQL 8.0.16+ syntax), Mermaid (ERD), Python (the posting test).

| File | What it is | Brief task |
|---|---|---|
| `design_notes.md` | The written answers, in the brief's order: money and time types, balance correctness, history, personal data, the four questions, the reporting model | all |
| `ddl.sql` | `CREATE TABLE` for 24 tables: keys, foreign keys, types, CHECK constraints, indexes | 1, 2 |
| `erd.png` / `erd.mmd` | Entity relationship diagram (Mermaid source and the rendered image) | 2 |
| `ledger_posting.sql` | `post_wallet_txn` and `reverse_wallet_txn`: the only way money moves (idempotent, locked, cache updated in the same transaction) | 3 |
| `test_ledger_posting.py` | Proves it on a throwaway database: replay, overdraft, reversal, 20 concurrent postings, CHECKs, cache = ledger | 3 |
| `seed.sql` | Fictitious data exercising every relationship: an accumulator, a split real/bonus stake, a forfeited bonus, a correction | 6 |
| `example_queries.sql` | Queries (a) to (d), plus the ledger chain check | 6 |
| `evidence/` | `example_queries_output.txt`, `ledger_posting_test.txt` | |
| `screenshots/` | The same two outputs as images | |

## Run it
```bash
mysql -u <user> -p < ddl.sql
mysql -u <user> -p jsb_platform < seed.sql
mysql -u <user> -p jsb_platform < ledger_posting.sql
mysql -u <user> -p jsb_platform < example_queries.sql
python test_ledger_posting.py          # DB_HOST / DB_PORT / DB_USER / DB_PASSWORD; uses its own database
```
The local setup (`../local_load/`) loads `ddl.sql` and `seed.sql` for you. The reporting model built on
top of these tables is in `../dbt_jsb_assessment/` and `../powerbi/`.
