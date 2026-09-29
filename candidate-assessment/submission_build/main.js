const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, LevelFormat, PageOrientation,
  Header, Footer, PageNumber, BorderStyle, ShadingType, VerticalAlign,
} = require("docx");
const {
  sections1_content, h1, h2, h3, p, pMixed, bullet, caption, imgPara, pageBreak,
  cell, table, BASE, NAVY, TEAL, GREY, LIGHT,
} = require("./build.js");

const W = 9360; // usable width at 0.75in margins on US Letter, in DXA

// ===========================================================================
// EXERCISE 1
// ===========================================================================
// One-page Finance Manager summary (brief: one page, including the bridge). Used as the
// first page of Exercise 1 here and written on its own as Finance_Summary.docx/.pdf.
function small(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, size: 18, ...opts })], spacing: { after: 60 } });
}
function smallBullet(text) {
  return new Paragraph({ children: [new TextRun({ text, size: 18 })], numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 } });
}
function subhead(text) {
  return new Paragraph({ children: [new TextRun({ text, bold: true, size: 22, color: TEAL })], spacing: { before: 140, after: 60 } });
}
// Same look as table(), with tighter padding so the summary fits one page.
function compactTable(headers, rows, widths) {
  const c = (text, width, opts = {}) => new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: opts.shade ? { type: ShadingType.CLEAR, fill: opts.shade } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 25, bottom: 25, left: 90, right: 90 },
    children: [new Paragraph({ children: [new TextRun({ text: String(text), size: 18, bold: !!opts.bold, color: opts.color })] })],
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => c(h, widths[i], { bold: true, shade: NAVY, color: "FFFFFF" })) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true,
        children: r.map((v, i) => c(v, widths[i], { shade: ri % 2 === 1 ? LIGHT : null, bold: r[0].startsWith("=") || r[0].startsWith("Residual") })) })),
    ],
  });
}
function financeSummary() {
  return [
    small("Week 1–7 September 2026 (UTC) · NAD · internal_deposits (326 rows) vs gateway_settlement (306 rows)", { italics: true, color: GREY }),
    new Paragraph({ spacing: { after: 80 }, children: [
      new TextRun({ text: "274 of 306 gateway settlements (90%) match exactly ", bold: true, size: 20 }),
      new TextRun({ text: "on reference, gross, fee and net. The 49 differences are 34 genuine breaks, 6 timing differences and 9 that are not a problem (exceptions.csv). The bridge from our R218,280.00 to the gateway's R217,979.97 leaves R0.00 unexplained; its two timing lines are provisional (see assumptions).", size: 20 }),
    ] }),
    subhead("Bridge on gross amounts: internal total → gateway total"),
    compactTable(
      ["Line", "NAD"],
      [
        ["Internal SUCCESS deposits, total", "218,280.00"],
        ["− Duplicate internal deposit rows (same settlement counted twice)", "(1,300.00)"],
        ["− Reversals / chargebacks (not in the gateway's SETTLED total)", "(850.00)"],
        ["− Deposits with no settlement yet (mid-week)", "(2,700.00)"],
        ["− Created in the last 15 min, not yet settled (provisional)", "(3,650.00)"],
        ["+ Settled in the first 15 min, no deposit this week (provisional)", "2,600.00"],
        ["+ Settlements with no internal record", "2,900.00"],
        ["+ Settled by the gateway but marked FAILED by us", "250.00"],
        ["+ Duplicate gateway settlement rows", "1,550.00"],
        ["+/− Gross amount differences with the gateway (net)", "900.00"],
        ["+/− Rounding (exactly 1 cent on 3 rows)", "(0.03)"],
        ["= Gateway SETTLED total", "217,979.97"],
        ["Residual (unexplained)", "0.00"],
      ],
      [7360, 2000]
    ),
    subhead("Priority actions"),
    compactTable(
      ["When", "Action", "Owner", "NAD"],
      [
        ["Today", "Re-credit 2 players: marked FAILED by us, settled by the gateway", "Payments", "250.00"],
        ["Today", "Get gateway detail for 4 unrecognised settlements (GW-000301 to 304)", "Payments", "2,900.00"],
        ["Week", "Dispute 4 gross differences (3 players under-credited R950, 1 over R50)", "Finance", "900.00 net"],
        ["Week", "Claim fee overcharges (4) and short-paid nets (2)", "Finance", "7.75"],
        ["Week", "Did 2 duplicate settlements pay twice? Audit 3 duplicate deposits", "Payments", "1,550 / 1,300"],
        ["Week", "Confirm the wallet debit for each of 3 reversals", "Finance", "850.00"],
        ["3 days", "5 deposits with no settlement: re-check next file, then escalate", "Finance", "2,700.00"],
      ],
      [800, 5960, 1100, 1500]
    ),
    subhead("Material assumptions"),
    smallBullet("Timing lines are provisional: this week's files can't prove them. R3,650 (3 deposits created 23:54–23:55 on 7 Sep) should appear in the 8–14 Sep gateway file; R2,600 (3 settlements at 00:04–00:06 on 1 Sep, GW-000331 to 333) should match the 25–31 Aug internal file. Finance keeps all six open until matched; any unmatched item becomes a break."),
    smallBullet("Fee = 2% of gross + R1.00, to the cent; any fee or net difference of 1 cent or more is flagged. Gross differences of exactly 1 cent (3 rows, R0.03) are treated as rounding, a materiality choice for Finance to confirm. Fee and net errors don't move gross, so they are actions, not bridge lines."),
      ];
}

const ex1 = [];
ex1.push(h1("Exercise 1 — Payment Gateway Reconciliation", { pageBreakBefore: true }));
ex1.push(new Paragraph({ children: [new TextRun({ text: "Finance Manager summary", bold: true, size: 26, color: TEAL })], spacing: { after: 60 } }));
ex1.push(...financeSummary());

ex1.push(new Paragraph({ text: "Supporting detail", heading: HeadingLevel.HEADING_2, pageBreakBefore: true, keepNext: true }));
ex1.push(p("Tools used: MySQL 8.0 for the schema, load and categorisation SQL; Python/pandas for the load script, CSV export and an independent cross-check of the bridge arithmetic.", { italics: true, color: GREY, size: 20 }));
ex1.push(h3("Approach"));
ex1.push(p("Both source files were loaded as-is into MySQL. Matching between internal_deposits.gateway_ref and gateway_settlement.merchant_ref uses a normalised reference (upper-case, letters and digits only), because the gateway returns six of our references with different punctuation, case or spacing (\"GW_000020\", \"GW000102\", \"gw-000196 \", \" GW-000267 \" and others). An exact-match join would misclassify those six clean matches as breaks."));
ex1.push(p("Every internal SUCCESS deposit and every gateway settlement row is either a clean match or one of twelve exception types: a genuine break, a timing difference, a business event (reversal), or not a problem at all. The rules live in exercise1-reconciliation/sql/03_reconciliation.sql and are ported into a dbt model (fct_recon_exceptions) so they run on a schedule with tests attached. The checks follow the brief's contract exactly: fee = 2% of gross + R1.00 to the cent, and net = gross − fee. Boundary tests at 1, 2 and 3 cents (sql/06_threshold_fixtures.py) confirm that every fee or net difference of a cent or more is flagged."));
ex1.push(...imgPara(`${BASE}/exercise1-reconciliation/screenshots/01_reconciliation_categories_and_bridge.png`, 480,
  "Actual output of sql/03_reconciliation.sql against MySQL 8.0, and of the independent row-by-row check."));

ex1.push(h3("Exceptions by category"));
ex1.push(p("Every one of the 49 rows in exceptions.csv carries exactly one classification, as the brief asks: genuine break (34), timing difference (6) or not a problem (9), plus a row-specific explanation, next step and owner. Reconciliation_Workbook.xlsx holds the same rows and the two raw files, with the bridge and category totals as live SUMIFS/COUNTIFS formulas that recalculate to a 0.00 residual."));
ex1.push(table(
  ["Category", "Classification", "Rows", "Impact (NAD)"],
  [
    ["Payment confirmed, wallet not credited", "Genuine break — act today", "2", "250.00 owed"],
    ["Unrecognised settlement (no internal record)", "Genuine break — act today", "4", "2,900.00"],
    ["Net amount is not gross minus fee", "Genuine break — dispute", "2", "4.00 short-paid"],
    ["Settled fee differs from contract", "Genuine break — dispute", "4", "3.75 overcharged"],
    ["Settled amount differs from internal amount", "Genuine break — dispute", "4", "-900.00 (net)"],
    ["Duplicate gateway settlement", "Genuine break — dispute", "4", "1,550.00*"],
    ["Duplicate internal deposit", "Genuine break — reverse credit", "6", "1,300.00*"],
    ["Reversal / chargeback", "Genuine break — claw back", "3", "850.00"],
    ["Deposit SUCCESS, no settlement found", "Genuine break — chase", "5", "2,700.00"],
    ["Created in the last 15 min (expected next week)", "Timing difference", "3", "3,650.00"],
    ["Settled in the first 15 min (likely last week's)", "Timing difference", "3", "2,600.00"],
    ["Rounding, exactly 1 cent", "Not a problem", "3", "0.03"],
    ["Reference formatting differs (matched)", "Not a problem", "6", "0.00"],
  ],
  [3700, 2560, 700, 1400]
));
ex1.push(p("* Amount carried by the duplicate row only; the original row in each pair is 0. Only SUCCESS deposits credit a wallet, so each duplicate internal deposit credited the player twice for one payment. A dbt test (assert_recon_bridge_reconciles) fails the build if the bridge residual is ever not exactly zero.", { italics: true, color: GREY, size: 18 }));
ex1.push(h3("Assumptions"));
ex1.push(bullet("Period 2026-09-01 00:00:00 to 2026-09-07 23:59:59 UTC inclusive; all times UTC; both files NAD only. Internal total = SUCCESS deposits; gateway total = SETTLED rows."));
ex1.push(bullet("References match after upper-casing and keeping only letters and digits. Fee = ROUND(2% × gross + 1.00, 2); any fee or net difference of 1 cent or more is a break; a gross difference of exactly 1 cent is rounding (Finance to confirm)."));
ex1.push(bullet("Cut-off window of 15 minutes at each end. Settlements arrive 28 min after the deposit on median, 50 min at most, and the nearest unexplained items are 2 hours or more from either boundary, so the result doesn't depend on the window. The six timing items stay provisional until matched."));
ex1.push(bullet("Reversals are genuine breaks until the wallet debit is confirmed. For duplicates, the later row is the duplicate. The bridge is on gross, so fee and net errors are actions, not bridge lines. FAILED deposits with no settlement agree on both sides and aren't listed."));

ex1.push(h3("How the figures were checked"));
ex1.push(p("The categorisation was implemented three times: the MySQL script, the dbt model, and separately written pandas code (sql/04_independent_check.py) that works per deposit and per settlement instead of through a join. All three agree on all 317 rows individually, and on every category's count and rand total."));
ex1.push(...imgPara(`${BASE}/exercise1-reconciliation/screenshots/02_three_way_agreement.png`, 520,
  "Three implementations, identical results in every category (sql/05_agreement_chart.py)."));
ex1.push(p("That check was added after an audit of an earlier draft found real problems, all now fixed. The draft had no test for net = gross − fee, which the brief requires, so it missed two short-paid settlements. It didn't quantify the fee overcharge. It counted four reference-formatting variants instead of six, because a case-insensitive database comparison hid three. It filed three start-of-week settlements as unrecognised money rather than timing. A later review by Codex found the fee check tolerated differences of up to 2 cents and a 2-cent gross difference could be labelled rounding; the rules are now exact, with boundary tests, and no figure changed. The bridge balanced throughout. The errors were in how the differences were labelled and summarised, which is why the categories are now cross-checked independently.", { italics: true }));

ex1.push(h3("Automating this daily"));
ex1.push(bullet("Land both feeds daily as-is, never overwriting, and log control totals (row count, sum) per source before matching. A source-declared-vs-received mismatch is itself an alert."));
ex1.push(bullet("Run the categorisation as a scheduled dbt model; persist history, never overwrite yesterday's result."));
ex1.push(bullet("Alert tiers: page immediately on \"wallet not credited\" or \"unrecognised settlement\"; same-day on new duplicates or disputes above a materiality threshold; daily digest for reversals and timing items still within the cut-off window."));
ex1.push(bullet("Ageing: unresolved after 3 days escalates to Finance management; unresolved after 7 days requires a signed-off write-off or credit note."));
// (page break handled by pageBreakBefore on the next heading)

// ===========================================================================
// EXERCISE 2
// ===========================================================================
const ex2 = [];
ex2.push(h1("Exercise 2 — Incremental, Restartable API Ingestion", { pageBreakBefore: true }));
ex2.push(p("Tools used: Python 3 (standard library HTTP, plus pymysql), MySQL 8 / MariaDB for the target and control tables (the brief allows any database; this one also holds the other exercises and dbt), Postman/Newman for the API contract.", { italics: true, color: GREY, size: 20 }));

ex2.push(h2("Design"));
ex2.push(bullet("Progress: a checkpoint table holds the last (updated_at, id) fully committed. Each run resumes with updated_since = that time (inclusive, per the API doc) and pages with the server's cursor. The API moves updated_at forward when a record changes, so one position covers new and changed records."));
ex2.push(bullet("No duplicates: id is the primary key and every write is an upsert on it. Repeated rows within a page are collapsed; a record is written only if it is new or its updated_at moved forward, so an older version never overwrites a newer one. A page's rows, its rejects, the checkpoint and the run counters commit in one transaction, so a kill loses at most the uncommitted page, which the next run re-reads."));
ex2.push(bullet("Failures: 429 waits for Retry-After; 500 and network errors retry with 2, 4, 8… s backoff, then the run ends FAILED with exit code 1 and the checkpoint unchanged. A database lock stops two scheduled runs overlapping; a run killed mid-way is marked ABANDONED by the next."));
ex2.push(bullet("Unclean data: numbers sent as strings are coerced; records with a missing player_id, an unparseable amount or time, or a negative amount go to ingest_rejects with the reason and raw JSON, once per distinct payload. The run carries on."));
ex2.push(bullet("Monitoring: ingest_runs records, per run, pages, new / changed / unchanged / rejected rows, 429 and 500 counts, start and end time, status and any error; the checkpoint is the last successful position. checks.sql holds the monitoring and alert queries."));

ex2.push(h2("Evidence: kill, restart, new activity"));
ex2.push(p("demo.py reproduces the whole sequence on any machine, with the mock API's faults switched on. Run 1 uses 50-record pages and a pause before each commit, and is hard-killed while page 2 is uncommitted. Only page 1 (50 rows) is in the table; the restart marks run 1 ABANDONED, resumes from the checkpoint and loads the rest."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/01_kill_restart_new_activity.png`, 560,
  "demo.py, steps 3–6: hard kill mid-page, restart from the checkpoint, check every id against the API."));
ex2.push(p("Run 3, straight after, finds nothing new or changed. After the interviewer's step (POST /admin/advance), run 4 loads exactly the 25 new and 40 changed records. verify_against_api.py then reads the whole API and compares id by id: 1,025 ids = 1,024 loaded + 1 quarantined (TX000777, missing player_id), with 0 missing, 0 stale versions and 0 duplicates. A live 500 and a 429 were retried along the way."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/08_new_activity_final_state.png`, 560,
  "demo.py, steps 7–10: rerun, new provider activity, incremental rerun, final state."));
ex2.push(p("The load continues incrementally into the reporting layer: the dbt model fct_api_transactions picks up only rows the ingestion stamped since its last run. incremental_demo.py shows 999 rows on the first build, 0 on a rerun, and exactly the 65 new and changed rows after the new activity, with the mart then equal to the source."));

ex2.push(h2("Checks and tests"));
ex2.push(bullet("checks.sql: duplicates, reject accounting, run history, stale or failed runs, and the last successful position."));
ex2.push(bullet("verify_against_api.py: every id in the table against the API (missing, unexpected, stale, duplicates); exits 1 on any mismatch."));
ex2.push(bullet("9 unit tests with no network or database: exit codes (401, exhausted 429 and 500 retries, success), the run lock, validation of unclean records, and the new / changed / unchanged classification."));

ex2.push(h2("API contract — Postman"));
ex2.push(p("A Postman collection documents the API's pagination, filtering, auth and admin-simulation behaviour, and includes a self-paginating request that walks every page and reports the total record count."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/02_postman_newman_run.png`, 560,
  "Newman run of the Exercise 2 collection."));

ex2.push(h2("Live run — Postman Desktop against the local mock API"));
ex2.push(p("The same collection was run in Postman Desktop on a Windows workstation against mock_api.py started from PyCharm, an independent environment from the one the code was built in."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/07_pycharm_mock_api_running.png`, 600,
  "mock_api.py running in PyCharm: \"Mock API on http://127.0.0.1:8000 (faults on)\"."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/03_postman_runner_config.png`, 460,
  "Collection Runner configuration: all seven requests, one iteration."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/05_postman_runner_pages_1_to_4.png`, 480,
  "Runner results, pages 1–4 of the self-paginating count. Page 1 returns 201 rows for limit=200 (an in-page repeated row); page 4 hits a live 500 and retries the same page."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/06_postman_runner_total_1027.png`, 480,
  "Runner results, pages 4–6: DONE — total rows returned by the API: 1,027 across 6 pages."));
ex2.push(p("Two assertions fail on request 2 (\"Next page\"), a one-shot documentation request with no retry logic that happened to land on an injected 429; only the counting request retries. 1,027 rather than 1,025 because the raw count includes the API's in-page repeated rows, which ingest.py collapses."));

ex2.push(h2("What I'd change for production"));
ex2.push(bullet("Scheduling: Airflow or cron every few minutes; the lock already makes overlapping runs harmless."));
ex2.push(bullet("Alerting: page on a non-zero exit code, a run stuck RUNNING past one interval, a rising reject rate, or checkpoint lag."));
ex2.push(bullet("Secrets: the API key and database password come from environment variables today; in production, from a secrets manager."));
ex2.push(bullet("Scale: bulk-load each page into a staging table and MERGE; partition by date; split id ranges across workers if the rate limit becomes the bottleneck."));
// ===========================================================================
// EXERCISE 3
// ===========================================================================
const ex3 = [];
ex3.push(h1("Exercise 3 — Database Design: Players, Wallets, Bets, Bonuses", { pageBreakBefore: true }));
ex3.push(p("Tools used: MariaDB 10.11 (MySQL 8.0.16+ syntax) for the schema, the posting procedures and the queries; Mermaid for the ERD; Python for the posting test; dbt for the reporting model.", { italics: true, color: GREY, size: 20 }));

ex3.push(h2("1–2. Tables, keys, types, constraints, indexes, and the ERD"));
ex3.push(...imgPara(`${BASE}/exercise3-schema-design/erd.png`, 620, "24 tables. Full CREATE TABLE statements in exercise3-schema-design/ddl.sql; the diagram is generated from erd.mmd."));
ex3.push(table(
  ["Area", "Tables and key decisions"],
  [
    ["Players", "players (no personal data) · player_identity (personal data only) · affiliates · SCD2 history for VIP tier, tags, and account status + KYC"],
    ["Wallets", "wallets (balance cache) · wallet_transactions (append-only ledger, the source of truth) · payment_methods · deposit_attempts · withdrawal_requests"],
    ["Bets", "One bets header per bet (stake split into real and bonus, plus the grant that paid the bonus part), with a detail table per product: sports_bet_details + bet_legs + sports_events; casino_round_details + games + game_providers; retail_bet_details + retail_locations + devices"],
    ["Bonuses", "bonus_campaigns (trigger, audience, rollover multiple, min odds, max stake, expiry) · player_bonuses (grant, progress, outcome) · bonus_rollover_events (each bet's contribution)"],
  ],
  [1600, 7760]
));
ex3.push(bullet("Money: DECIMAL(18,4), never FLOAT or DOUBLE, which can't hold 0.10 exactly. Odds are DECIMAL(10,3); currency is CHAR(3)."));
ex3.push(bullet("Time: DATETIME(6), always UTC, in columns named *_at_utc. TIMESTAMP is avoided because it converts through the session time zone. Microseconds keep the order of events within a second."));
ex3.push(bullet("Keys: every table has a primary key and every relationship has a foreign key. Natural keys are unique, so a retry can't duplicate: ledger idempotency_key, bet and withdrawal request_id, deposit gateway_ref, one reversal per ledger row."));
ex3.push(bullet("39 CHECK constraints, including: amounts > 0; balance_after = balance_before ± amount; a reversal must point at what it reverses; manual adjustments need a reason; a bonus stake needs its grant; an accumulator has at least 2 legs."));
ex3.push(bullet("Indexes on the access paths: ledger (wallet, time) and (player, time) for balances; bets (product, settled time) for NGR; deposits (player, time); bonus links for campaign cost; (player, valid_to) on each history table."));

ex3.push(h3("Requirements traceability and deliberate extensions"));
ex3.push(p("The brief names capabilities, not tables. Every one of the 24 tables maps to a stated requirement, either directly or as the normalisation or control that requirement needs. The full matrix is in SCHEMA_REQUIREMENTS_TRACEABILITY.md, and no table is an unexplained extension."));
ex3.push(bullet("player_status_history is retained on purpose. The brief lists player status (active, blocked, self-excluded) and KYC status and asks for regulator queries. A current value on players can't answer \"was this player self-excluded, or unverified, when the bet was placed?\"; an SCD2 history can. It sits alongside the VIP-tier and tag histories the brief names."));
ex3.push(bullet("Normalisation the brief implies: payment_methods; the product detail and reference tables (sports events and legs; casino games and providers; retail locations and devices); and bonus_rollover_events, which makes rollover progress auditable. There is no separate bonus-outcome table: player_bonuses.status and resolved_at_utc record completed, expired and forfeited."));

ex3.push(h2("3. How a balance is calculated and guaranteed"));
ex3.push(p("A balance is the sum of the ledger up to a moment; wallets.real_balance and bonus_balance are only a cache. Money moves only through two procedures (ledger_posting.sql). post_wallet_txn locks the wallet row, returns the original row if the idempotency key was already posted, refuses an overdraft, writes the ledger row with balance_before and balance_after, and updates the cache, all in one transaction. A reversal (reverse_wallet_txn) is a new, opposite row pointing at the original, which is never edited, and a row can only be reversed once. A correction is a reversal plus the right posting. A dbt test fails the build if any cache differs from its ledger."));
ex3.push(...imgPara(`${BASE}/exercise3-schema-design/screenshots/02_ledger_posting_test.png`, 520, "test_ledger_posting.py on a throwaway database: replay, overdraft, reversal, 20 concurrent postings and the CHECK constraints. All pass."));

ex3.push(h2("4–5. History, and protecting personal information"));
ex3.push(bullet("History: VIP tier, tags, and account status + KYC are SCD Type 2 tables. A change closes the current row and opens a new one, so \"what tier was this player on 3 September?\" and \"was this player self-excluded when the bet was placed?\" have answers. Money history is the ledger itself; bonus progress is event-sourced."));
ex3.push(bullet("Personal data: only player_identity holds names, date of birth, ID number and contact details. Everything else uses the surrogate player_id, and the reporting layer never reads the identity table. Access is one restricted, logged role; the ID number is encrypted in the application with a KMS key; erasure anonymises the identity row and leaves the financial history intact."));

ex3.push(h2("6. The four questions — verified output"));
ex3.push(p("Definitions: GGR = stakes − payouts on bets settled in the month. Bonus cost = the bonus money wagered on those bets, so NGR = GGR − bonus cost. An unwagered bonus that expires or is forfeited costs nothing; the unwagered part of an active bonus is a liability. No levy is modelled, because the brief doesn't give one."));
ex3.push(...imgPara(`${BASE}/exercise3-schema-design/screenshots/01_example_queries_output.png`, 560, "example_queries.sql against the seed data (MariaDB 10.11)."));
ex3.push(table(
  ["Query", "Result (September 2026, NAD)"],
  [
    ["(a) NGR by product for a month", "casino 270.00 · retail 100.00 · sportsbook −150.00 (GGR −110.00 less 40.00 bonus cost) · total 220.00"],
    ["(b) Bonus cost as % of NGR, by campaign", "Registration Bonus: 40.00 = 18.18% of NGR. Bonus stakes are traced to the grant that paid them, and the grant to its campaign"],
    ["(c) A player's balance at a date and time", "Player 1 at 2026-09-06 00:00: 1,160.00. Player 2: 450.00 while a wrong credit stood, 415.00 after its reversal and the correct posting"],
    ["(d) Deposits that failed, then succeeded", "Player 2: failed 09:00, succeeded 09:04, 4 minutes later"],
  ],
  [3400, 5960]
));
ex3.push(p("The same answers come from the dbt marts, the Power BI expected values and the Databricks notebook."));

ex3.push(h2("7. From operational design to a reporting model"));
ex3.push(p("The dbt project (dbt_jsb_assessment/) builds a star schema: dim_player, dim_player_vip_tier_scd, dim_campaign and dim_date around three facts, each at one grain. fact_bet has one row per bet, with GGR, bonus cost, NGR and the paying campaign. fact_wallet_transaction has one row per ledger movement, loaded incrementally. fact_bonus_transaction has one row per grant, with its cost and outstanding liability. Two marts answer queries (a) and (b), and personal data never enters the model. The same project also runs Exercise 1's reconciliation as a tested model."));
ex3.push(...imgPara(`${BASE}/dbt_jsb_assessment/screenshots/01_dbt_build.png`, 440, "dbt build across all three exercises: 78 of 78 pass (24 models, 54 tests), 0 errors. Every mart has a primary key; two models load incrementally."));
// (page break handled by pageBreakBefore on the next heading)

// ===========================================================================
// POWER BI
// ===========================================================================
const pbi = [];
pbi.push(h1("Power BI — Reporting Data Model and Report", { pageBreakBefore: true }));
pbi.push(p("Tools used: Power BI project format (.pbip), generated by a Python script from one set of definitions, with the dbt marts embedded as data.", { italics: true, color: GREY, size: 20 }));
pbi.push(p("The dbt marts become a Power BI project, JSB_Assessment.pbip, covering all three exercises. The semantic model has 11 tables, 7 relationships and 28 DAX measures (22 calculations and 6 colour rules for the KPI tiles), and the report has four pages. The data is embedded in the project, so it opens and refreshes on any machine with no folder path or database connection to set up. The same script writes the model, the report pages, the readable DAX file and a list of expected values, then validates them, so the four cannot drift apart."));
pbi.push(...imgPara(`${BASE}/powerbi/model.png`, 600, "Power BI model view for Exercise 3: three dimensions filter three facts. Facts are not joined to each other."));
pbi.push(h2("Modelling decisions worth calling out"));
pbi.push(bullet("Facts are not joined to facts. fact_wallet_transaction keeps related_bet_id and related_player_bonus_id as drill-through keys only. Relating them would give dim_player two filter paths to the wallet table. Power BI rejects that as an ambiguous model, and in any tool it is a source of silently wrong numbers. The build script checks every pair of tables and refuses to build if any pair has more than one path."));
pbi.push(bullet("Money is fixed decimal (Currency.Type, 4 dp, matching DECIMAL(18,4)), and the CSVs are parsed with en-US culture. A South African regional setting, which uses a comma as the decimal separator, therefore can't misread 200.0000."));
pbi.push(bullet("The Exercise 1 and 2 tables (fct_recon_exceptions, mart_recon_bridge, ingest_runs, transactions) stand alone. They share no keys with the player model, so they have no relationships to it, and a filter on one page can't leak into another."));
pbi.push(h2("Measures"));
pbi.push(table(
  ["Measure", "Definition"],
  [
    ["GGR", "Stakes − payouts on settled (won/lost) bets"],
    ["Bonus Cost (realised)", "Bonus money wagered on settled bets"],
    ["NGR", "GGR − Bonus Cost (realised) — query (a)"],
    ["Campaign Bonus Cost / % of NGR", "Bonus money wagered from each campaign's grants, ÷ total NGR — query (b)"],
    ["Bonus Liability Outstanding", "Unwagered part of bonuses still active: owed, not yet a cost"],
    ["Balance as of selected date", "Sum of the ledger up to the last date in the date filter — query (c)"],
    ["Settlements Matched Exactly / Exceptions", "Counts of OK rows and of every other category in fct_recon_exceptions"],
    ["Act Now Value", "Impact of the two act-now categories: settled but marked FAILED, and unrecognised settlements"],
    ["Bridge Amount / Bridge Residual", "Sum of the bridge steps; residual = gateway total − steps, which must be 0.00"],
    ["Transactions Loaded / Runs / Rows Rejected / Retries", "Exercise 2's loaded rows and run log"],
  ],
  [3400, 5960]
));
pbi.push(h2("Report pages and expected values"));
pbi.push(bullet("NGR overview (Ex. 3): GGR, realised bonus cost, NGR and bonus liability cards; GGR vs NGR by product; bonus cost as a percentage of NGR by campaign."));
pbi.push(bullet("Player balances (Ex. 3): a date slicer, deposits, and each player's balance rebuilt from the ledger as of the slicer's end date."));
pbi.push(bullet("Reconciliation (Ex. 1): headline cards, the bridge as a waterfall from the internal total to the gateway total, exceptions by category, and a detail table."));
pbi.push(bullet("Ingestion monitoring (Ex. 2): loaded rows, runs, rejected rows and rate-limit retries; the run history, including the run killed mid-page; transactions by status."));
pbi.push(p("Each value below was computed from the CSVs with pandas, independently of the DAX, and matches the MySQL, MariaDB and dbt results. The full list is in powerbi/expected_values.md."));
pbi.push(table(
  ["Visual", "Expected value"],
  [
    ["GGR / Bonus Cost (realised) / NGR / Liability", "260.00 / 40.00 / 220.00 / 10.00"],
    ["NGR by product", "casino 270.00 · retail 100.00 · sportsbook −150.00"],
    ["Registration Bonus: cost / % of NGR", "40.00 / 18.18%"],
    ["Player 1 balance, slicer ending 2026-09-06", "1,160.00 (real)"],
    ["Balances, full date range", "Player 1: 890.00 · Player 2: 415.00 · Player 3: 90.00 real + 10.00 bonus"],
    ["Settlements matched exactly / exceptions", "274 / 43"],
    ["Act Now Value / Bridge Residual", "3,150.00 / 0.00"],
    ["Waterfall", "218,280.00 → 217,979.97 in 10 adjustment steps"],
    ["Transactions loaded / runs / rows rejected / API retries", "1,024 / 4 / 1 / 1"],
    ["Transactions by status", "completed 587 · failed 214 · pending 207 · reversed 16"],
  ],
  [4200, 5160]
));
pbi.push(h2("How it was verified"));
pbi.push(p("Power BI Desktop doesn't run in the Linux environment this was built in. Instead, the build script checks that every visual field, sort and DAX reference resolves to the model, that every CSV's columns match the model, that every relationship column exists, and that no filter path is ambiguous. A negative test confirmed it rejects an ambiguous relationship and a misspelled measure. The report layout follows the supplied Demo.pbix (Power BI Desktop 2.130, CY24SU06 theme)."));
pbi.push(p("Power BI Desktop has since opened an earlier version of this project on a Windows machine: the pages and visuals loaded. The one failure was that the data folder path didn't exist on that machine, and embedding the data removes that step. If Desktop objects to the project for any other reason, powerbi/README.md gives a five-minute manual route to build the same model in Demo.pbix."));
pbi.push(p("Building this layer also caught a real defect upstream. The seed data's wallet balance cache didn't match its own ledger, breaking the rule that the ledger is the truth. The seed was fixed, and a dbt test (assert_wallet_cache_matches_ledger) now fails the build if the two ever diverge. The test failed on the old data and passes on the corrected data."));

// ===========================================================================
// DATABRICKS
// ===========================================================================
const dbx = [];
const RUN = "https://dbc-ea48b979-9753.cloud.databricks.com/?o=7474649344710062#job/308746372139777/run/";
dbx.push(h1("Databricks — The Same Three Exercises on Delta Lake", { pageBreakBefore: true }));
dbx.push(p("Tools used: Databricks Free Edition (serverless compute, Unity Catalog, Delta Lake); open-source Spark 4 + Delta 4 for the local test.", { italics: true, color: GREY, size: 20 }));
dbx.push(p("The three exercises also run as Databricks notebooks. build_notebooks.py generates them from the project's own files, so they can't drift from the MySQL version: the two Exercise 1 CSVs, the Exercise 2 mock API and the retry and validation code from ingest.py, and Exercise 3's ddl.sql translated to Delta plus seed.sql. Each notebook ends with checks that fail loudly if a figure differs from the MySQL and dbt results."));
dbx.push(table(
  ["Notebook", "What it does", "Checks"],
  [
    ["01_exercise1_reconciliation", "Loads both files with an idempotent MERGE (twice, to prove no duplicates), categorises every row and builds the bridge", "17: every category's count and value equal MySQL/dbt; bridge residual 0.00"],
    ["02_exercise2_incremental_ingestion", "Serves the supplied mock API inside the notebook and loads it into Delta with MERGE. Crashes on purpose between a page and its checkpoint, restarts, then loads new activity", "6: table equals the API after the restart and after new activity; exactly 25 new and 40 changed; crashed run ABANDONED; one reject"],
    ["03_exercise3_schema", "The 24 tables in Delta with 39 enforced CHECK constraints and Unity Catalog keys, the seed data and the four queries", "9: negative stake refused; no duplicate on 44 keys; no orphan on 32 foreign keys; the four answers; cache = ledger"],
  ],
  [2600, 3960, 2800]
));
dbx.push(h2("Run on the Databricks workspace"));
dbx.push(p("On 2026-09-28, one job ran the three notebooks in order (ex1 → ex2 → ex3) on serverless compute. All three tasks succeeded, and all 32 checks passed, the same total as the local test."));
dbx.push(table(
  ["Task", "Result", "Run id"],
  [
    ["Job: JSB assessment – all exercises", "SUCCESS", "460654207301296"],
    ["ex1 — reconciliation", "SUCCESS · 17/17 PASS", "453545434689160"],
    ["ex2 — incremental ingestion", "SUCCESS · 6/6 PASS", "340425981901042"],
    ["ex3 — schema design", "SUCCESS · 9/9 PASS", "685793852884612"],
  ],
  [3800, 2800, 2760]
));
dbx.push(p("Run pages: " + RUN + "<run id>. The full URLs are in databricks/evidence/databricks_run.md.", { size: 18, color: GREY }));
dbx.push(h2("What Databricks changes, and what it needed"));
dbx.push(bullet("Keys: Unity Catalog primary and foreign keys are declared but not enforced, and there is no UNIQUE. Loads therefore MERGE on the key, and the notebooks check every key for duplicates and every foreign key for orphans. CHECK and NOT NULL are enforced by Delta, and the notebook proves it by trying a negative stake."));
dbx.push(bullet("Restartability: Delta commits one table at a time, so writes are ordered data → rejects → checkpoint → counters, each an idempotent MERGE. A crash re-reads at most one page, and re-applying it changes nothing. Setting the job's Maximum concurrent runs to 1 replaces MySQL's GET_LOCK."));
dbx.push(bullet("Two fixes only a real serverless run could show. First, serverless refuses connections to 127.0.0.1 and to fixed ports, so on Databricks the mock API binds an OS-assigned port and is called by host name. Second, Delta requires a generated column's type to match exactly, and DECIMAL(18,4) + DECIMAL(18,4) is DECIMAL(19,4), so generated expressions are now cast to the column type. No check was changed, and the local test still passes."));
dbx.push(...imgPara(`${BASE}/databricks/screenshots/01_local_test_run.png`, 520, "The same notebooks on open-source Spark 4 + Delta 4 (run_local.py): all 32 checks pass."));

// ===========================================================================
// ASSEMBLE
// ===========================================================================
const numbering = {
  config: [{
    reference: "bullets",
    levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 480, hanging: 240 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 960, hanging: 240 } } } },
    ],
  }],
};

const doc = new Document({
  creator: "Candidate submission",
  title: "JSB Data Engineer — Practical Exercises: Candidate Submission",
  numbering,
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 21 } },
    },
    heading1: { run: { color: NAVY, size: 32, bold: true }, paragraph: { spacing: { before: 400, after: 200 } } },
    heading2: { run: { color: TEAL, size: 26, bold: true } },
    heading3: { run: { color: GREY, size: 22, bold: true, italics: true } },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, bottom: 1080, left: 1440, right: 1440 },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 4 } },
            children: [new TextRun({ text: "JSB Data Engineer — Practical Exercises", size: 16, color: GREY })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: "Page ", size: 16, color: GREY }),
              new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY }),
              new TextRun({ text: " of ", size: 16, color: GREY }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: GREY }),
            ],
          })],
        }),
      },
      children: [
        ...sections1_content,
        ...ex1,
        ...ex2,
        ...ex3,
        ...pbi,
        ...dbx,
      ],
    },
  ],
});

const summaryDoc = new Document({
  creator: "Candidate submission",
  title: "Payment gateway reconciliation — Finance Manager summary",
  numbering,
  styles: { default: { document: { run: { font: "Calibri", size: 21 } } } },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
                           margin: { top: 900, bottom: 900, left: 1440, right: 1440 } } },
    children: [
      new Paragraph({ children: [new TextRun({ text: "Payment gateway reconciliation — Finance Manager summary", bold: true, size: 30, color: NAVY })], spacing: { after: 60 } }),
      ...financeSummary(),
    ],
  }],
});
Packer.toBuffer(summaryDoc).then((buf) => {
  fs.writeFileSync("/home/user/Libstar-Product-Analytics/candidate-assessment/exercise1-reconciliation/Finance_Summary.docx", buf);
  console.log("summary written, bytes:", buf.length);
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/home/user/Libstar-Product-Analytics/candidate-assessment/JSB_Candidate_Submission.docx", buf);
  console.log("written, bytes:", buf.length);
});
