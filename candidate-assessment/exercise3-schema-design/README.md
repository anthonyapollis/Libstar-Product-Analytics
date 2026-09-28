# Exercise 3 — Database design for players, wallets, bets and bonuses

**Tools:** MySQL 8.0, Mermaid (ERD).

## Files
| File | What it is |
|---|---|
| `ddl.sql` | Full `CREATE TABLE` statements — 23 tables, PKs/FKs/types/constraints/indexes. Runs clean on MySQL 8.0 (`mysql -u <user> -p < ddl.sql`). |
| `erd.mmd` / `erd.png` | Entity-relationship diagram (Mermaid source + rendered image). |
| `seed.sql` | Minimal seed data exercising every relationship, so the example queries return real results. |
| `example_queries.sql` | The four required queries (a–d), run against the seed data. |
| `design_notes.md` | Money/time types, balance correctness, SCD2 history, PII protection, and the OLTP → reporting model mapping. |
| `evidence/example_queries_output.txt` | Captured output of the four queries. |

## Run it
```bash
mysql -u <user> -p < ddl.sql
mysql -u <user> -p jsb_platform < seed.sql
mysql -u <user> -p jsb_platform < example_queries.sql
```
