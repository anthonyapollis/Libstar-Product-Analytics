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
      new TextRun({ text: "on reference, gross, fee and net. The bridge from our R218,280.00 to the gateway's R217,979.97 leaves R0.00 unexplained. Two of its timing lines are provisional until the adjacent weeks' files confirm them (see assumptions).", size: 20 }),
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
ex1.push(table(
  ["Category", "Type", "Rows", "Impact (NAD)"],
  [
    ["Payment confirmed, wallet not credited", "Break — act now", "2", "250.00"],
    ["Unrecognised settlement (no internal record)", "Break — act now", "4", "2,900.00"],
    ["Net amount is not gross minus fee", "Break — dispute", "2", "4.00 short-paid"],
    ["Settled fee differs from contract", "Break — dispute", "4", "3.75 overcharged"],
    ["Settled amount differs from internal amount", "Break — dispute", "4", "-900.00 (net)"],
    ["Duplicate gateway settlement", "Break — dispute", "4", "0.00*"],
    ["Duplicate internal deposit", "Break — dedupe", "6", "0.00*"],
    ["Reversal / chargeback", "Business event", "3", "850.00"],
    ["Deposit SUCCESS, no settlement found", "Timing / possible break", "5", "2,700.00"],
    ["Created in the last 15 min (expected next week)", "Timing — provisional", "3", "3,650.00"],
    ["Settled in the first 15 min (likely last week's)", "Timing — provisional", "3", "2,600.00"],
    ["Rounding, exactly 1 cent", "Not a problem", "3", "0.03"],
  ],
  [3700, 1900, 700, 1760]
));
ex1.push(p("* The deposit and settlement amounts match on these rows, so the row-level impact is 0. The real cost is the duplicate itself: a double-credit risk, or a disputed double settlement. The bridge accounts for each separately. A dbt test (assert_recon_bridge_reconciles) fails the build if the bridge residual is ever not exactly zero.", { italics: true, color: GREY, size: 18 }));

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
ex2.push(p("Tools used: Python 3 (standard library urllib only — no HTTP framework dependency), MySQL 8.0 for the checkpoint/ledger tables, Postman/Newman for exercising and documenting the API contract.", { italics: true, color: GREY, size: 20 }));

ex2.push(h2("Design"));
ex2.push(bullet("Progress lives in MySQL (ingest_checkpoint), not memory or a local file, so any process on any host can resume it. Each run resumes from updated_since = last processed updated_at (inclusive), then paginates within the run via the server's cursor."));
ex2.push(bullet("Every write is an upsert (INSERT … ON DUPLICATE KEY UPDATE) keyed on the provider's id — replaying a page is always safe. The data upsert, the reject-quarantine insert, the checkpoint update, and the run counters are committed together in one transaction per page."));
ex2.push(bullet("429 (rate limited): sleep for Retry-After, retry the same request. 500 / network errors: exponential backoff. Bad records (unparseable amount, missing player_id): quarantined with the reason and the full raw JSON — never silently dropped."));
ex2.push(bullet("Every run writes one row to ingest_runs: pages fetched, rows upserted/rejected, 429/500 counts, status. A run stuck RUNNING past one scheduling interval is the signal a stale-run monitor pages on."));

ex2.push(h2("Evidence: kill, restart, new activity"));
ex2.push(p("The process was started with a small page size and an artificial pre-commit delay, then killed with SIGKILL mid-page — a hard crash, not a graceful shutdown."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/01_kill_restart_new_activity.png`, 560,
  "Actual terminal output: kill mid-page → restart → complete → simulate new provider activity → rerun."));
ex2.push(p("Result: 50 rows committed before the kill (exactly page 1 — page 2 never landed), the run left visibly RUNNING (the stale-run signal), and a clean restart resumed correctly with zero duplicates and zero missing rows. After simulating new activity (POST /admin/advance), a rerun correctly picked up 40 changed records and 25 new ones — including a live 429 that was retried automatically."));

ex2.push(h2("API contract — Postman"));
ex2.push(p("A Postman collection documents the API's pagination, filtering, auth and admin-simulation behaviour, and includes a self-paginating request that walks every page and reports the total record count directly in Postman's Test Results panel."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/02_postman_newman_run.png`, 560,
  "Newman run of the Exercise 2 collection: 5 requests, 10/10 assertions passing."));

ex2.push(h2("Live run — Postman Desktop against the local mock API"));
ex2.push(p("The same collection was then imported into Postman Desktop on a Windows workstation and run against mock_api.py started from PyCharm — an independent environment from the one the code was built in."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/07_pycharm_mock_api_running.png`, 600,
  "mock_api.py running in PyCharm: \"Mock API on http://127.0.0.1:8000 (faults on)\"."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/03_postman_runner_config.png`, 460,
  "Collection Runner configuration: all seven requests, one iteration."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/05_postman_runner_pages_1_to_4.png`, 480,
  "Runner results, pages 1–4 of the self-paginating count. Page 1 returns 201 rows for limit=200 (the API's documented in-page duplicate); page 4 hits a live 500 and retries the same page."));
ex2.push(...imgPara(`${BASE}/exercise2-ingestion/screenshots/06_postman_runner_total_1027.png`, 480,
  "Runner results, pages 4–6: DONE — total records returned by the API: 1,027 across 6 pages."));
ex2.push(p("The run reports 16 of 18 assertions passing. The two failures are on request 2 (\"Next page\"), a one-shot documentation request with no retry logic, which happened to land on the mock API's injected 429. Only the counting request carries retry handling. That is by design, and it shows why the ingestion program retries every call."));
ex2.push(p("Why 1,027 rather than 1,025: the runner executes /admin/advance (request 5) before the count, so the dataset is already 1,025 records; the extra rows are the API's deliberate in-page duplicates, counted raw here. ingest.py deduplicates them, which is why its loaded row count is lower than the raw count."));

ex2.push(h2("What I'd change for production"));
ex2.push(bullet("A managed scheduler (Airflow / cron+systemd) with a concurrency lock, so two overlapping runs can't race."));
ex2.push(bullet("Secrets (API key, DB credentials) out of source and into a secrets manager."));
ex2.push(bullet("Page on FAILED runs, a stale RUNNING row, or a rejects-rate spike (usually a schema change, not random dirty data)."));
ex2.push(bullet("At real volume: staging-table + bulk MERGE instead of row-by-row upserts; partition by date; multiple workers on disjoint id ranges if one API key's rate limit becomes the bottleneck."));
// (page break handled by pageBreakBefore on the next heading)

// ===========================================================================
// EXERCISE 3
// ===========================================================================
const ex3 = [];
ex3.push(h1("Exercise 3 — Database Design: Players, Wallets, Bets, Bonuses", { pageBreakBefore: true }));
ex3.push(p("Tools used: MySQL 8.0 for the schema (cross-verified against MariaDB 10.11), Mermaid for the ERD, dbt for the reporting-model mapping.", { italics: true, color: GREY, size: 20 }));

ex3.push(h2("Entity-relationship diagram"));
ex3.push(...imgPara(`${BASE}/exercise3-schema-design/erd.png`, 620, "23-table operational schema — full DDL in exercise3-schema-design/ddl.sql, verified to run clean on both MySQL 8.0 and MariaDB 10.11."));

ex3.push(h2("Design principles"));
ex3.push(h3("Money and time"));
ex3.push(p("DECIMAL(18,4) everywhere a balance or amount is stored — never FLOAT/DOUBLE. DATETIME(6), always UTC, columns suffixed _at_utc; MySQL's TIMESTAMP is deliberately avoided because it silently converts using the session/server time zone."));
ex3.push(h3("Balance correctness"));
ex3.push(p("wallets.real_balance / bonus_balance are a materialised cache, not the source of truth — wallet_transactions (an append-only ledger) is. A balance at any point in time is SUM(credit) − SUM(debit) up to that moment, proven directly by example query (c) below. Corrections and reversals are new rows referencing the original (reversal_of_wallet_txn_id), never edits; every row carries a deterministic idempotency_key so replaying an event can never double-post it. A dbt test (assert_wallet_cache_matches_ledger) fails the build if the cache ever disagrees with the ledger."));
ex3.push(h3("History over time"));
ex3.push(p("player_vip_tier_history and player_tag_history are SCD Type 2 (a new row per change, valid_from/valid_to), so \"what tier was this player on 3 September\" is answerable, not just \"what tier are they now\"."));
ex3.push(h3("Protecting personal information"));
ex3.push(p("player_identity is a separate table, joined only by player_id — every other table (bets, wallet transactions, bonuses) never sees a name or ID number. In production: application-layer encryption on sensitive fields, a dedicated low-privilege DB role, and every read of the identity table logged."));

ex3.push(h2("The four required queries — verified output"));
ex3.push(p("Run against the seed data in exercise3-schema-design/seed.sql; identical results on MySQL 8.0 and MariaDB 10.11."));
ex3.push(...imgPara(`${BASE}/exercise3-schema-design/screenshots/01_example_queries_output.png`, 560, "mysql -- jsb_platform -- example_queries.sql"));
ex3.push(table(
  ["Query", "Result"],
  [
    ["(a) NGR by product for a month", "sportsbook -160.00 · casino -30.00 · retail 100.00 (NAD)"],
    ["(b) Bonus cost as % of NGR, by campaign", "Registration Bonus: -27.78% (matches the dbt mart's independently-computed figure exactly)"],
    ["(c) A player's balance at a given date/time", "Reconstructed purely from the ledger (SUM), not a stored column — proves the design"],
    ["(d) Deposits that failed, then later succeeded", "Self-join on deposit_attempts finds the failed→success pair, 4 minutes apart"],
  ],
  [3400, 5960]
));

ex3.push(h2("Operational design → reporting model"));
ex3.push(p("A dbt project (dbt_jsb_assessment/) builds a star schema on top of this operational design: conformed dimensions (dim_player, dim_date, dim_campaign — dim_player_vip_tier_scd carries the same Type-2 history pattern through to the reporting layer) surrounding grain-specific facts (fact_bet, fact_wallet_transaction, fact_bonus_transaction). Two reusable marts answer queries (a) and (b) directly, and — extended during this review — the project now also covers Exercise 1's reconciliation as a scheduled, tested model."));
ex3.push(...imgPara(`${BASE}/dbt_jsb_assessment/screenshots/01_dbt_build.png`, 440, "dbt build across all three exercises: 67/67 pass (23 models, 44 tests), 0 errors."));
// (page break handled by pageBreakBefore on the next heading)

// ===========================================================================
// POWER BI
// ===========================================================================
const pbi = [];
pbi.push(h1("Power BI — Reporting Data Model and Report", { pageBreakBefore: true }));
pbi.push(p("Tools used: Power BI project format (.pbip), generated by a Python script from one set of definitions, with the dbt marts embedded as data.", { italics: true, color: GREY, size: 20 }));
pbi.push(p("The dbt marts become a Power BI project, JSB_Assessment.pbip, covering all three exercises. The semantic model has 11 tables, 7 relationships and 20 DAX measures, and the report has four pages. The data is embedded in the project, so it opens and refreshes on any machine with no folder path or database connection to set up. The same script writes the model, the report pages, the readable DAX file and a list of expected values, then validates them, so the four cannot drift apart."));
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
    ["Bonus Cost (realised)", "Bonus money staked on bets that lost"],
    ["NGR", "GGR − Bonus Cost (realised) — query (a)"],
    ["Campaign Bonus Cost / % of NGR", "Granted amount of resolved bonuses, ÷ total NGR — query (b)"],
    ["Bonus Liability Outstanding", "Granted amount of bonuses still active: owed, not yet a cost"],
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
    ["GGR / Bonus Cost (realised) / NGR", "-70.00 / 20.00 / -90.00"],
    ["NGR by product", "sportsbook -160.00 · casino -30.00 · retail 100.00"],
    ["Registration Bonus: cost / % of NGR", "25.00 / -27.78%"],
    ["Player 1 balance, slicer ending 2026-09-06", "1,160.00 (real)"],
    ["Balances, full date range", "Player 1: 1,190.00 · Player 2: 400.00 · Player 3: 100.00 real + 30.00 bonus"],
    ["Settlements matched exactly / exceptions", "274 / 43"],
    ["Act Now Value / Bridge Residual", "3,150.00 / 0.00"],
    ["Waterfall", "218,280.00 → 217,979.97 in 10 adjustment steps"],
    ["Transactions loaded / runs / rows rejected / retries", "1,024 / 3 / 1 / 1"],
    ["Transactions by status", "completed 587 · failed 214 · pending 207 · reversed 16"],
  ],
  [4200, 5160]
));
pbi.push(h2("How it was verified"));
pbi.push(p("Power BI Desktop doesn't run in the Linux environment this was built in. Instead, the build script checks that every visual field, sort and DAX reference resolves to the model, that every CSV's columns match the model, that every relationship column exists, and that no filter path is ambiguous. A negative test confirmed it rejects an ambiguous relationship and a misspelled measure. The report layout follows the supplied Demo.pbix (Power BI Desktop 2.130, CY24SU06 theme)."));
pbi.push(p("Power BI Desktop has since opened an earlier version of this project on a Windows machine: the pages and visuals loaded. The one failure was that the data folder path didn't exist on that machine, and embedding the data removes that step. If Desktop objects to the project for any other reason, powerbi/README.md gives a five-minute manual route to build the same model in Demo.pbix."));
pbi.push(p("Building this layer also caught a real defect upstream. The seed data's wallet balance cache didn't match its own ledger, breaking the rule that the ledger is the truth. The seed was fixed, and a dbt test (assert_wallet_cache_matches_ledger) now fails the build if the two ever diverge. The test failed on the old data and passes on the corrected data."));

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
