// Builds Employee360_DQ_eBook.docx. Tables are read from outputs/*.csv, so no figure is typed by hand.
// Run through build_pdf.py (two passes, so the contents and the requirements index carry real page numbers).
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, ImageRun, PageBreak, LevelFormat, VerticalAlign, Header, Footer, PageNumber,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "outputs");
const IMG = path.join(ROOT, "ebook", "img");
const NAVY = "1F3864", TEAL = "0E7C7B", GREY = "595959", LIGHT = "EEF3F8", AMBER = "FFF4E0", RED = "B42318";
const PAGES = fs.existsSync(path.join(__dirname, "pages.json")) ? JSON.parse(fs.readFileSync(path.join(__dirname, "pages.json"))) : {};

// ---------- data ----------
function csv(name) {
  const text = fs.readFileSync(path.join(OUT, name), "utf8").replace(/\r/g, "");
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows.filter(r => r.length > 1 || r[0]);
  return body.map(r => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}
const money = v => "R" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
const monitoring = csv("monitoring.csv");
const reconSummary = csv("recon_summary.csv");
const reconFields = csv("recon_fields.csv");
const totals = csv("recon_salary_totals.csv")[0];
const counts = csv("recon_counts.csv");
const profileCounts = csv("profile_counts.csv");
const nulls = csv("profile_nulls.csv");
const patterns = csv("profile_patterns.csv");
const lookalike = csv("recon_lookalike.csv")[0];
const runs = csv("incremental_runs.csv");
const goldVs = csv("medallion_gold_vs_delivered.csv");
const layers = csv("medallion_layers.csv");
const blocking = monitoring.filter(r => r.blocks_release === "True");

// ---------- building blocks ----------
function png(file) { const b = fs.readFileSync(file); return { b, w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
const FIGURES = [];  // evidence index
function figure(file, width, caption, kind, source) {
  const full = path.join(IMG, file), { b, w, h } = png(full);
  FIGURES.push({ file: `ebook/img/${file}`, kind, source, sha: crypto.createHash("sha256").update(b).digest("hex") });
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160, after: 60 },
      children: [new ImageRun({ data: b, type: "png", transformation: { width, height: Math.round(h * width / w) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Figure ${FIGURES.length}. ${caption}`, italics: true, size: 17, color: GREY }),
                 new TextRun({ text: `  [${kind}]`, size: 15, color: TEAL })] }),
  ];
}
const HEADINGS = []; let n1 = 0, n2 = 0;
function h1(text, opts = {}) {
  let label = text;
  if (opts.num) { n1++; n2 = 0; label = `${n1}. ${text}`; HEADINGS.push({ num: String(n1), label, key: opts.key }); }
  else if (opts.appendix) { label = `Appendix ${opts.appendix}. ${text}`; HEADINGS.push({ num: opts.appendix, label, key: opts.key }); }
  else if (opts.key) { HEADINGS.push({ num: opts.key, label, key: opts.key }); }
  return new Paragraph({ text: label, heading: HeadingLevel.HEADING_1, pageBreakBefore: opts.pageBreakBefore !== false, spacing: { after: 160 } });
}
function h2(text, opts = {}) {
  n2++; const label = `${n1}.${n2} ${text}`;
  HEADINGS.push({ num: `${n1}.${n2}`, label, key: opts.key });
  return new Paragraph({ text: label, heading: HeadingLevel.HEADING_2, keepNext: true, keepLines: true, spacing: { before: 260, after: 120 } });
}
const where = (...keys) => {
  const hs = keys.map(k => HEADINGS.find(h => h.key === k)).filter(Boolean);
  return [hs.map(h => /^\d+$/.test(h.num) ? `Ch. ${h.num}` : (/^[A-Z]$/.test(h.num) ? `App. ${h.num}` : (h.num.includes(".") ? `§${h.num}` : h.label))).join(", "),
          hs.map(h => PAGES[h.num] ?? "–").join(", ")];
};
function p(text, o = {}) { return new Paragraph({ spacing: { after: 140 }, children: [new TextRun({ text, ...o })] }); }
function runs_(parts) { return parts.map(x => typeof x === "string" ? new TextRun(x) : new TextRun(x)); }
function pm(parts, o = {}) { return new Paragraph({ spacing: { after: 140 }, ...o, children: runs_(parts) }); }
function bullet(parts) { return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 70 }, children: runs_(Array.isArray(parts) ? parts : [parts]) }); }
function answers(text) {
  return new Paragraph({ keepNext: true, shading: { type: ShadingType.CLEAR, fill: LIGHT }, indent: { left: 120 }, spacing: { after: 160 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: TEAL, space: 6 } },
    children: [new TextRun({ text: "Answers  ", bold: true, size: 18, color: TEAL }), new TextRun({ text, size: 18, color: GREY })] });
}
function box(title, lines, fill = LIGHT, color = NAVY) {
  return new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [9360], rows: [new TableRow({ children: [new TableCell({
    width: { size: 9360, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill }, margins: { top: 120, bottom: 120, left: 180, right: 180 },
    borders: Object.fromEntries(["top", "bottom", "left", "right"].map(s => [s, { style: BorderStyle.SINGLE, size: 6, color }])),
    children: [new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, color, size: 21 })] }),
               ...lines.map(l => new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 50 }, children: runs_(Array.isArray(l) ? l : [l]).map(r => r) }))],
  })] })] });
}
function table(head, rows, widths, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, w, hdr, i, align) => new TableCell({
    width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: { type: ShadingType.CLEAR, fill: hdr ? NAVY : (i % 2 ? "F7F9FC" : "FFFFFF") },
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: align || AlignmentType.LEFT, children: [new TextRun({ text: String(t), bold: hdr, color: hdr ? "FFFFFF" : "000000", size: o.size || 17 })] })],
  });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [
    new TableRow({ tableHeader: true, cantSplit: true, children: head.map((h, j) => cell(h, widths[j], true, 0, o.align?.[j])) }),
    ...rows.map((r, i) => new TableRow({ cantSplit: true, children: r.map((c, j) => cell(c, widths[j], false, i, o.align?.[j])) })),
  ] });
}
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });
const R = AlignmentType.RIGHT;

// ---------- content ----------
const body = [];

// 1. Profile
body.push(h1("Profile: what the three files look like", { num: true, key: "profile" }));
body.push(answers("Task 1 · inspect with SQL: counts, distinct keys, null rates, duplicates, an unexpected pattern or freshness concern"));
body.push(pm(["Three CSV extracts for the October 2026 snapshot: HR (system of record for who works here, status, manager, department, location), payroll (salary, payroll status) and the delivered Employee 360 view under test. The SQL is ", { text: "sql/01_profile.sql", font: "Consolas", size: 18 }, "; it runs unchanged on Databricks and on local Spark."]));
body.push(h2("Rows, keys and duplicates", { key: "profile.counts" }));
body.push(table(["Source", "Rows", "Distinct IDs", "Duplicate rows"], profileCounts.map(r => [r.source, r.row_count, r.distinct_ids, r.duplicate_rows]), [3360, 2000, 2000, 2000], { align: [0, R, R, R] }));
body.push(gap());
body.push(box("Insight: the counts agree, the contents do not", [
  "All three files have exactly 48 rows. A row-count check, the usual first control, passes.",
  `Yet payroll has ${profileCounts[1].distinct_ids} distinct employees (E1015 appears twice with different salaries), and only ${counts[2].employee_360} of Employee 360's IDs exist in HR.`,
]));
body.push(h2("Blanks, freshness and unexpected patterns", { key: "profile.patterns" }));
body.push(table(["Source", "Column", "Blank", "%"], nulls.map(r => [r.source, r.column_name, r.null_count, r.null_pct]), [2600, 3160, 1800, 1800], { align: [0, 0, R, R] }));
body.push(gap());
body.push(table(["Pattern", "Rows", "Examples"], patterns.map(r => [r.pattern, r.rows_affected, r.example_ids || "–"]), [6160, 1000, 2200], { align: [0, R, 0] }));
body.push(gap());
body.push(bullet([{ text: "Freshness: ", bold: true }, "payroll's pay period is 2026-09 for an October snapshot, so salaries are a month behind (acceptable, but it matters for leavers). E1030 has not been touched for 99 days."]));
body.push(bullet([{ text: "Format: ", bold: true }, "HR writes dates as yyyy/MM/dd, the other files as ISO. A loader that assumes ISO turns every HR date into NULL, silently."]));
body.push(h2("Not every difference is an error", { key: "profile.judgement" }));
body.push(table(["Observation", "Verdict", "Why"], [
  ["E1040 location “CPT” vs “Cape Town”", "Not an error", "Same place; compared on the standard name"],
  ["E1042 HR effective date 19 Nov", "Legitimate exception", "Future-dated change: the October snapshot should still show the October value"],
  ["E1001–E1005 have no manager", "Allowed", "They head departments (they manage others)"],
  ["23 HR rows updated before their effective date", "Normal", "Changes keyed in ahead of time"],
  ["E1029 terminated in HR, payable in payroll", "Inconsistent: confirm", "September pay may be due, but the two later leavers are already stopped"],
], [3300, 1800, 4260]));

// Top findings
body.push(h2("Top three findings and why they matter", { key: "profile.top3" }));
body.push(answers("Task 1 · identify your top three findings and explain their business significance"));
body.push(box("1 · Employee 360 lists the wrong people and wrong values. Release must be blocked", [
  "E1027 (active, paid R80,300) is missing; E1099 “Unknown Legacy Employee” is present instead and is a field-for-field copy of E1028.",
  "E1012 is shown Active although HR terminated them; E1018's salary is R6,500 too high; E1037's USD amount is relabelled ZAR; E1044 has a salary with no payroll record.",
  `Significance: reported headcount is 46 active against HR's 45, and the salary total is off by a net ${money(totals.net_difference)} that hides ${money(totals.gross_difference)} of gross error.`,
]));
body.push(gap());
body.push(box("2 · A leaver is still payable (E1029). Alert payroll before the October cut-off", [
  "HR terminated E1029 on 2026-10-02; payroll still says Payable (R84,200 a month). E1012 and E1041, who left later, are already Stopped.",
  "E1044 is the mirror case: active in HR with no payroll record at all (possibly unpaid).",
  "Significance: an overpayment that must later be recovered, or an employee not paid. Both are people and compliance risks, not just data risks.",
], AMBER, "9A6700"));
body.push(gap());
body.push(box("3 · Payroll, the salary system of record, cannot be trusted for two employees", [
  "E1015 has two payroll rows (R57,100 and R58,600). Employee 360 shows the first, but nobody can say which is right.",
  "E1037's salary is in USD in a column that should only hold ZAR.",
  "Significance: until payroll is fixed, salary for these employees is reported as “cannot verify”. Guessing would hide the problem.",
]));

// 2. Checks
body.push(h1("Executable data-quality checks", { num: true, key: "checks" }));
body.push(answers("Task 2 · 4–6 automated checks across at least three dimensions; advanced SQL; PySpark; return affected employee IDs"));
body.push(p("Six checks in sql/02_checks.sql, one per dimension. Each is a view that returns one row per affected employee (rule, employee_id, source, detail), so an empty view means pass and a failure always names who is affected."));
body.push(table(["Rule", "Dimension", "What it checks", "Technique"], [
  ["DQ01", "Uniqueness", "employee_id unique in every source", "window count over a union of sources"],
  ["DQ02", "Completeness", "mandatory HR fields; blank manager only for heads", "self-join (who manages others), filter(array)"],
  ["DQ03", "Referential integrity", "manager_id exists in HR", "LEFT ANTI JOIN"],
  ["DQ04", "Consistency", "HR status agrees with payroll status", "CTE + LEFT JOIN, missing payroll counted"],
  ["DQ05", "Validity", "salary is a positive ZAR amount; pay period well formed", "RLIKE, CASE"],
  ["DQ06", "Freshness", "updated within 30 days of the extract", "datediff over a union of sources"],
], [900, 1900, 3600, 2960]));
body.push(...figure("term_checks.png", 600, "Output of the six checks: every failure names the employee.", "Rendered log", "outputs/logs/run_local.log → ebook/captures/term_checks.txt"));
body.push(h2("PySpark: field-level reconciliation", { key: "checks.pyspark" }));
body.push(p("reconcile_fields() in the notebook compares every business-critical field of Employee 360 with the system that owns it (HR or payroll), using null-safe equality, and classifies each difference as an Error, a Legitimate exception or Cannot verify, with the reason. It is the PySpark task the brief asks for, and it feeds rules RC03 and RC04."));
body.push(h2("How the checks were verified", { key: "checks.verified" }));
body.push(p("tests/check_expected.py recomputes every rule's affected IDs from the raw CSVs in plain Python, with separately written logic and no Spark, and compares them with the Spark output. It runs in seconds, so it can run on every pull request."));
body.push(...figure("term_independent.png", 470, "Independent recomputation: all 10 rules agree with the Spark output.", "Rendered log", "outputs/logs/check_expected.log → ebook/captures/term_independent.txt"));

// 3. Reconciliation
body.push(h1("Reconciliation: sources to Employee 360", { num: true, key: "recon" }));
body.push(answers("Task 3 · missing downstream, unexpected downstream, field mismatches; why agreeing totals do not prove correctness; a short summary"));
body.push(h2("Summary", { key: "recon.summary" }));
body.push(table(["Measure", "Value"], reconSummary.map(r => [r.measure, r.value]), [7360, 2000], { align: [0, R] }));
body.push(gap());
body.push(table(["Employee", "Field", "Source", "Employee 360", "Classification"], reconFields.map(r => [r.employee_id, r.field, r.source_value || "blank", r.e360_value || "blank", r.classification]), [1100, 2000, 1800, 1800, 2660]));
body.push(h2("Why agreeing totals prove nothing", { key: "recon.totals" }));
body.push(...figure("term_counts.png", 620, "Row counts agree (48/48/48) while the key sets differ; E1099 matches E1028 on 8 of 8 attributes.", "Rendered log", "outputs/logs/run_local.log → ebook/captures/term_counts.txt"));
body.push(...figure("chart_net_vs_gross.png", 560, `One net figure (${money(totals.net_difference)}) hides four errors worth ${money(totals.gross_difference)} gross.`, "Chart from data", "outputs/recon_salary_totals.csv"));
body.push(box("Insight: reconcile keys and fields, not totals", [
  "A missing employee and an invented one cancel exactly in a headcount.",
  "Salary errors in both directions cancel in a total: +R82,200, −R80,300, +R56,200, +R6,500.",
  "Only a key-level and field-level comparison against the system of record finds them.",
]));

// 4. Root cause
body.push(h1("Root cause: E1099 appears, E1027 disappears", { num: true, key: "rootcause" }));
body.push(answers("Task 4 · evidence, likely point of failure, business impact, what would confirm it, who should fix it; facts kept apart from hypotheses"));
body.push(table(["Proven facts (evidence in outputs/)", "Hypothesis (not proven)"], [[
  `E1027 is in HR (Active) and payroll (Payable, R80,300) but not in Employee 360 (recon_keys.csv). E1099 exists only in Employee 360. E1099 equals E1028 (${lookalike.lookalike_name}) on ${lookalike.attributes_equal_of_8} of 8 attributes (recon_lookalike.csv). E1099's last_updated (2026-10-08) is the build date stamped on all current rows, so this build wrote it. The 48-row count did not change.`,
  "The identity-resolution step that assigns employee_id in the Employee 360 build (for example a legacy-ID crosswalk) produced a second record carrying E1028's attributes under the legacy key E1099, and the same step may be why the neighbouring ID E1027 was dropped. Alternative: a manual legacy insert copied an existing row while a separate filter excluded E1027.",
]], [4680, 4680]));
body.push(gap());
body.push(bullet([{ text: "Related pattern (hypothesis): ", bold: true }, "Employee 360 carries values the current extracts do not contain (E1020's department, E1044's salary, E1012's pre-termination status). The build may keep the previous value when the source is blank or missing."]));
body.push(bullet([{ text: "What would confirm it: ", bold: true }, "the crosswalk or MDM entries for E1027, E1028 and E1099; the Employee 360 table's Delta history (DESCRIBE HISTORY, VERSION AS OF) to see when E1099 appeared and E1027 went; the 2026-10-08 job logs and merge logic; HR confirming that no E1099 exists."]));
body.push(bullet([{ text: "Business impact: ", bold: true }, "people reporting lists the wrong people while headcount and cost look plausible; anything fed by Employee 360 (access, org charts) inherits the error."]));
body.push(bullet([{ text: "Who should fix it: ", bold: true }, "the Employee 360 data engineering team (owner of the build and the crosswalk) with the MDM or HR data steward. Release stays blocked by RC01 and RC02 until it is fixed."]));

// 5. Monitoring
body.push(h1("Monitoring output and release decision", { num: true, key: "monitoring" }));
body.push(answers("Task 5 · rule, pass/fail, affected count, severity, affected IDs; an alert threshold; what blocks a release and what is monitored"));
body.push(...figure("chart_monitoring.png", 580, `All 10 rules fail; ${blocking.length} block release.`, "Chart from data", "outputs/monitoring.csv"));
body.push(table(["Rule", "Status", "Count", "Severity", "Action", "Alert when >", "Affected IDs"], monitoring.map(r => [r.rule_id, r.status, r.affected_count, r.severity, r.action, r.alert_when_affected.replace("> ", ""), r.affected_ids]), [700, 800, 750, 1000, 1400, 1000, 3710], { align: [0, 0, R, 0, 0, R, 0], size: 16 }));
body.push(gap());
body.push(bullet([{ text: "Block release ", bold: true }, "(any failure stops this Employee 360 build being published): wrong people, wrong or unverifiable pay, invalid currency, duplicate keys."]));
body.push(bullet([{ text: "Alert now ", bold: true }, "(owner told the same day; publishing may continue): the fix is in a source system. DQ04, a leaver still payable, goes to payroll before the pay-run cut-off."]));
body.push(bullet([{ text: "Monitor ", bold: true }, "(trend, alert only above a threshold): e.g. alert when more than 1 employee (2% of 48) has a blank mandatory field; freshness alerts when more than 2 records are stale."]));
body.push(...figure("term_release.png", 470, "The gate's decision for this delivery.", "Rendered log", "outputs/logs/run_local.log → ebook/captures/term_release.txt"));

// 6. Medallion + incremental
body.push(h1("Pipeline: Bronze, Silver, Gold, incremental", { num: true, key: "pipeline" }));
body.push(answers("Task 6 · minimise repeated full-table scans and noisy alerts; how the checks sit in a Databricks pipeline"));
body.push(...figure("diagram_pipeline.png", 620, "How the checks sit in the pipeline: a blocking failure stops publication; owners hear about new issues only.", "Generated diagram", "ebook/pipeline.mmd"));
body.push(h2("Layers", { key: "pipeline.layers" }));
body.push(table(["Layer", "Table", "Rows"], layers.map(r => [r.layer, r.table_name, r.row_count]), [1500, 5860, 2000], { align: [0, 0, R] }));
body.push(gap());
body.push(table(["Measure", "Gold", "Delivered Employee 360"], goldVs.map(r => [r.measure, r.gold, r.delivered_e360 || "–"]), [5360, 2000, 2000], { align: [0, R, R] }));
body.push(gap());
body.push(box("Insight: Gold shows what correct looks like", [
  "Gold is rebuilt from Silver by the ownership rules: HR decides who exists and their status; payroll supplies salary only when it holds exactly one valid ZAR value.",
  "It has E1027 and not E1099, shows E1012 as Terminated and gives E1018's salary as R62,900. 45 active employees, the same as HR.",
  "Salaries for E1015, E1037 and E1044 are left empty and flagged, not guessed. 40 of 48 records are fully trusted.",
]));
body.push(h2("Incremental runs and the issue lifecycle", { key: "pipeline.incremental" }));
body.push(p("Each delivery is MERGEd into Bronze on a row hash. An extract whose file hash matches the last one is not read at all. Failures are MERGEd into dq_issues (open, resolved), and alerts go out only for issues that are new in a run. Run 3 uses a labelled, simulated delivery (data/simulated_run3) with three fixes and one new problem."));
body.push(table(["Run", "Delivery", "Employees changed", "Checks", "New (alerted)", "Resolved", "Open"], runs.map(r => [r.run_id, r.batch_dir, r.changed_employees, r.checks_run === "True" ? "ran" : "skipped", r.new_issues, r.resolved_issues, r.open_issues]), [600, 2400, 1500, 1000, 1360, 1200, 1300], { align: [0, 0, R, 0, R, R, R] }));
body.push(...figure("chart_issue_lifecycle.png", 560, "Run 2 reads nothing; run 3 alerts on 2 new issues, not on the 11 still open.", "Chart from data", "outputs/incremental_runs.csv"));
body.push(...figure("term_incremental.png", 560, "The three runs: batches loaded or skipped, changed employees, and the only two alerts.", "Rendered log", "outputs/logs/run_incremental_local.log → ebook/captures/term_incremental.txt"));

// 7. Operations
body.push(h1("Running it in Azure Databricks and Azure DevOps", { num: true, key: "ops" }));
body.push(answers("Task 6 · what runs before deployment, on a schedule, who is alerted; compute cost, scans, noisy alerts, paid tools; one check not run every time"));
body.push(table(["When", "What runs", "Databricks cost"], [
  ["Every pull request", "run_local.py on the fixture CSVs and tests/check_expected.py (must be 10/10), on the build agent with local PySpark", "none"],
  ["Merge to main", "databricks bundle validate and deploy -t test, then one smoke run on the fixtures", "one short run"],
  ["Release", "databricks bundle deploy -t prod behind an approval gate", "none"],
  ["Daily 06:00 (prod)", "The medallion job: Bronze load, checks with fail_on_block=true, Silver and Gold; publish runs only if the checks task succeeds", "minutes, serverless"],
], [1900, 5960, 1500]));
body.push(gap());
body.push(bullet([{ text: "Alerts: ", bold: true }, "DQ04 (leaver still payable) to payroll and HR operations the same day, re-checked three working days before the pay run; a blocking failure to the Employee 360 on-call through the job's failure notification; High rules to the HR data steward for new issues only; Medium rules in a weekly digest."]));
body.push(bullet([{ text: "Compute: ", bold: true }, "serverless jobs compute (nothing billed between runs); unchanged extracts skipped by file hash; only new or changed rows written; at scale the row-level checks filter to the changed keys the notebook already lists."]));
body.push(bullet([{ text: "Noise: ", bold: true }, "one issue per rule and employee; alert once when it opens, close it when it stops failing."]));
body.push(bullet([{ text: "Tools: ", bold: true }, "plain SQL and PySpark in the same job, history in Delta tables; no separate data-quality or observability licence. The same SQL runs on open-source Spark, so CI needs no workspace."]));
body.push(box("A check I would not run on every execution", [
  "The full profile (every column of every table) and the look-alike search (a self-join that grows with the square of the table).",
  "They give diagnostic insight, not a pass/fail gate, and their answers change slowly: run them weekly and during an investigation.",
], AMBER, "9A6700"));

// 8. Databricks evidence (only if the run record exists)
const dbxMd = path.join(ROOT, "evidence", "databricks_run.md");
if (fs.existsSync(dbxMd)) {
  body.push(h1("Proof on Databricks", { num: true, key: "databricks" }));
  body.push(answers("Tasks 2 and 6 · the same notebooks run on Databricks serverless; results compared with the local run"));
  const md = fs.readFileSync(dbxMd, "utf8").split("\n").filter(l => l.trim() && !l.startsWith("|---"));
  for (const l of md.slice(0, 60)) {
    if (l.startsWith("#")) body.push(new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, children: [new TextRun(l.replace(/^#+\s*/, ""))] }));
    else body.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: l.replace(/\*\*/g, "").replace(/`/g, ""), size: 17, font: l.startsWith("|") ? "Consolas" : undefined })] }));
  }
  for (const f of fs.readdirSync(IMG).filter(f => f.startsWith("databricks_")).sort())
    body.push(...figure(f, 600, f.replace(/^databricks_|\.png$/g, "").replace(/_/g, " "), "Databricks run export", "evidence/databricks_run.md"));
}

// 9. AI use
body.push(h1("AI use", { num: true, key: "ai" }));
body.push(answers("AI use · tools and what they sped up; one suggestion corrected or rejected; how it was verified; commercial value"));
body.push(bullet([{ text: "Tools: ", bold: true }, "Claude Code (Anthropic) drafted and ran the SQL, PySpark, runners and these notes; Codex (OpenAI) reviewed the branch independently. Judgement calls (what is an error, severity, ownership) were not delegated."]));
body.push(bullet([{ text: "Corrected: ", bold: true }, "the first PySpark reconciliation used groupBy().agg(F.first()), which is non-deterministic in Spark and let E1015 pass silently because Employee 360 matched one of two conflicting salaries. The independent profile caught it; the fix takes values in file order and adds a Cannot verify class."]));
body.push(bullet([{ text: "Also corrected: ", bold: true }, "a draft claim that the salary gap was under 0.3% (it is 2.6%, and the real story is net against gross); a QUALIFY clause that runs on Databricks but not on open-source Spark, rewritten so one SQL file runs in both."]));
body.push(bullet([{ text: "Verification: ", bold: true }, "the independent plain-Python recomputation (10/10), the same code on Databricks and locally, and every finding traceable to an output file and employee ID."]));
body.push(bullet([{ text: "Commercial value: ", bold: true }, "worth it for mechanical, checkable work (scaffolding, harness, drafts); no time saved on judgement, and some spent on verification, which the silent-pass example shows is necessary. With real client data, only a client-approved assistant inside the client's tenancy, or schemas and synthetic samples only."]));

// Appendix A
body.push(h1("Files, how to run, assumptions, limitations", { appendix: "A", key: "appA" }));
body.push(answers("What to submit · SQL, PySpark and scripts in Git; outputs; README with run instructions, assumptions and limitations"));
body.push(table(["Path", "What it is"], [
  ["sql/00_staging.sql … 03_reconciliation.sql", "Typed staging, profile, six checks, key and totals reconciliation"],
  ["sql/10_silver_gold.sql", "Silver and Gold layers"],
  ["notebooks/employee360_dq.py", "Databricks notebook: runs the SQL, PySpark reconcile_fields, monitoring, release gate"],
  ["notebooks/employee360_incremental.py, employee360_medallion.py", "Incremental Bronze load, issue lifecycle, Silver and Gold"],
  ["run_local.py, run_incremental_local.py", "Run the notebooks on local PySpark (+ Delta) and save outputs/"],
  ["tests/check_expected.py", "Independent plain-Python recomputation of every rule"],
  ["outputs/*.csv, outputs/logs/", "Every result in this book, and the run logs"],
  ["databricks.yml, azure-pipelines.yml", "Bundle job and CI/CD pipeline (not executed: no Azure project available)"],
  ["docs/, README.md", "Notes, assumptions, limitations, video script"],
], [4200, 5160]));
body.push(gap());
body.push(pm([{ text: "Run locally: ", bold: true }, { text: "pip install \"pyspark==4.0.*\" \"delta-spark==4.0.*\"; python run_local.py; python tests/check_expected.py; python run_incremental_local.py", font: "Consolas", size: 17 }]));
body.push(bullet([{ text: "Assumptions: ", bold: true }, "employee_id is the join key; HR owns status, manager, department, location; payroll owns salary, currency and payroll status; extract date 2026-10-08; stale = not updated in 30 days; future-dated = HR effective date after 31 October; CPT = Cape Town; payroll period 2026-09 is the latest for the October snapshot."]));
body.push(bullet([{ text: "Limitations: ", bold: true }, "databricks.yml and azure-pipelines.yml were not executed; run 3 of the incremental demo uses a labelled simulated delivery; the root cause is a hypothesis until the crosswalk, Delta history and job logs are seen; at this size the row-level checks re-run on the full snapshot when anything changes."]));

// Appendix B (evidence index) is appended after FIGURES is complete.

// ---------- front matter ----------
const cover = [
  new Paragraph({ spacing: { before: 1800 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Data Quality Assurance · Technical Challenge", size: 26, color: GREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 120 }, children: [new TextRun({ text: "Employee 360", bold: true, size: 64, color: NAVY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: "What is wrong, why it matters, and how to stop it recurring", size: 30, color: TEAL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: TEAL, space: 8 } }, spacing: { after: 900 }, children: [new TextRun({ text: "Profiling · six data-quality checks · reconciliation · root cause · monitoring · Bronze/Silver/Gold · Azure Databricks and DevOps", size: 20, color: GREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Tools", bold: true, size: 21 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: "Spark SQL · PySpark 4.0 · Delta Lake · Databricks (serverless) · Python · Mermaid · Azure DevOps (pipeline definition)", size: 19, color: GREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: "AI coding assistants (Claude Code and Codex) were used during development and review; every result was executed and checked independently (Chapter 9).", size: 18, color: GREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 900 }, children: [new TextRun({ text: "Every number in this book is read from the output of running the code shown. All data is synthetic. Amounts in ZAR.", italics: true, size: 18, color: GREY })] }),
];

const front = [];
front.push(h1("Contents", { pageBreakBefore: true }));
const CW = [1100, 7060, 1200];
front.push(table(["No.", "Title", "Page"], HEADINGS.map(h => [/^[A-Z]$/.test(h.num) ? `App. ${h.num}` : h.num, h.label.replace(/^(\d+(\.\d+)?\.?|Appendix [A-Z]\.)\s*/, ""), PAGES[h.num] ?? "–"]), CW, { align: [0, 0, R], size: 18 }));

front.push(h1("Executive summary", { key: "exec" }));
front.push(box("The decision: BLOCK this Employee 360 release", [
  `All 10 rules fail; ${blocking.length} of them (${blocking.map(r => r.rule_id).join(", ")}) block publication.`,
  "Employee 360 is missing a real employee (E1027) and contains an invented one (E1099, a copy of E1028); it shows a terminated employee as active and carries salaries that cannot be traced or verified.",
], "FDECEC", RED));
front.push(gap());
front.push(h1("Five things worth knowing", { pageBreakBefore: false }));
[
  ["Counts and totals lie. ", `48 rows in every file, yet the key sets differ; the salary gap nets to ${money(totals.net_difference)} but is ${money(totals.gross_difference)} gross across four employees.`],
  ["The wrong people are listed. ", `E1099 matches E1028 on ${lookalike.attributes_equal_of_8} of 8 attributes and was written by the current build; E1027 vanished. The likely failure point is the identity or crosswalk step (hypothesis).`],
  ["A leaver may be overpaid. ", "E1029 left on 2 October and is still payable at R84,200 a month, while later leavers are stopped. Payroll should confirm before the October cut-off."],
  ["Some salaries cannot be verified. ", "Payroll holds two salaries for E1015 and a USD amount for E1037. The checks say “cannot verify” instead of guessing."],
  ["Correct is buildable. ", "The Gold layer rebuilt from the sources by ownership rules has 45 active employees (as HR), the right people, and 40 of 48 fully trusted records."],
].forEach(([b, t], i) => front.push(new Paragraph({ spacing: { after: 110 }, children: [new TextRun({ text: `${i + 1}.  ${b}`, bold: true, color: NAVY }), new TextRun(t)] })));
front.push(pm([{ text: "How to read this book. ", bold: true }, "Chapters 1–5 answer tasks 1–5 of the brief in order; chapters 6–7 answer task 6; chapter 9 answers the AI questions. Each section opens with an “Answers” tag naming the part of the brief it covers. Every figure is labelled with its kind: rendered log (real run output drawn as an image, excerpt kept beside it), chart from data, generated diagram or Databricks run export. Appendix B lists every image with its source and SHA-256."], { spacing: { before: 160 } }));

front.push(h1("Requirements index: where each part of the brief is answered"));
const QW = [800, 5560, 1900, 1100];
const Q = [
  ["1", "Profile with SQL: counts, distinct keys, null rates, duplicates", "profile.counts", "profile.patterns"],
  ["1", "At least one unexpected pattern or freshness concern", "profile.patterns"],
  ["1", "Top three findings and their business significance", "profile.top3", "exec"],
  ["2", "4–6 automated checks across at least three dimensions", "checks"],
  ["2", "Advanced SQL (joins, CTEs, window functions)", "checks"],
  ["2", "PySpark for a substantive validation or reconciliation", "checks.pyspark"],
  ["2", "Return affected employee IDs, not only pass/fail counts", "checks", "monitoring"],
  ["2", "Disclose limitations if Spark cannot run", "checks.verified", "appA"],
  ["3", "Employees missing downstream, unexpected downstream records", "recon.summary"],
  ["3", "Field-level mismatches for business-critical fields", "recon.summary"],
  ["3", "Prove why agreeing totals do not establish correctness", "recon.totals"],
  ["3", "Short reconciliation summary", "recon.summary"],
  ["4", "Evidence, point of failure, impact, confirming information, owner", "rootcause"],
  ["4", "Distinguish proven facts from hypotheses", "rootcause"],
  ["5", "Monitoring output: rule, pass/fail, count, severity, IDs", "monitoring"],
  ["5", "An alert threshold; what blocks a release vs is monitored", "monitoring"],
  ["6", "How checks run in Azure Databricks and Azure DevOps CI/CD", "ops"],
  ["6", "Before deployment, on a schedule, who receives alerts", "ops"],
  ["6", "Minimise compute, full-table scans, noisy alerts, paid tools", "pipeline.incremental", "ops"],
  ["6", "One check not to run on every execution, and why", "ops"],
  ["AI", "Tools used and what they accelerated", "ai"],
  ["AI", "One AI suggestion corrected, simplified, challenged or rejected", "ai"],
  ["AI", "How it was verified; was it commercially justified", "ai"],
  ["Submit", "SQL, PySpark and scripts in Git; README with run, assumptions, limitations", "appA"],
  ["Submit", "Profiling, validation, reconciliation, monitoring outputs, root-cause note", "profile", "checks", "recon", "rootcause", "monitoring"],
];
front.push(table(["Task", "Brief requirement", "Answered in", "Page"], Q.map(([t, text, ...keys]) => { const [s, pg] = where(...keys); return [t, text, s, pg]; }), QW, { align: [0, 0, 0, R], size: 16 }));
front.push(p("The 5–10 minute video is recorded separately; its script is docs/walkthrough_script.md.", { italics: true, size: 17, color: GREY }));

// Appendix B: evidence index (after all figures are known)
body.push(h1("Evidence index", { appendix: "B", key: "appB" }));
body.push(p("Every image in this book, what kind it is and where it came from. Check any file with sha256sum <path>."));
body.push(table(["Fig.", "File", "Kind", "Source", "SHA-256 (first 16)"], FIGURES.map((f, i) => [String(i + 1), f.file.replace("ebook/img/", ""), f.kind, f.source, f.sha.slice(0, 16)]), [600, 2300, 1500, 3260, 1700], { size: 15 }));

// ---------- document ----------
const doc = new Document({
  creator: "Employee 360 DQ", title: "Employee 360 data quality",
  styles: { default: { document: { run: { font: "Calibri", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, color: TEAL }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 21, bold: true, color: NAVY }, paragraph: { outlineLevel: 2 } },
    ] },
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "Employee 360 · data quality", size: 16, color: GREY })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Page ", size: 16, color: GREY }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY }), new TextRun({ text: " of ", size: 16, color: GREY }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: GREY })] })] }) },
    children: [...cover, ...front, ...body],
  }],
});
// headings.json: what build_pdf.py looks for (front-matter headings first, then numbered ones)
fs.writeFileSync(path.join(__dirname, "headings.json"), JSON.stringify(HEADINGS.map(h => ({ num: h.num, label: h.label })), null, 1));
Packer.toBuffer(doc).then(b => fs.writeFileSync(path.join(ROOT, "Employee360_DQ_eBook.docx"), b));
