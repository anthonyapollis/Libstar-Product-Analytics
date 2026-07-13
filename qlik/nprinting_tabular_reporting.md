# Report distribution: NPrinting vs Qlik Cloud Tabular Reporting

You asked to incorporate **NPrinting**. Key platform fact:

> Qlik NPrinting is a Windows, client-managed product. It connects to Qlik
> Sense Enterprise on Windows (or QlikView) — it **cannot** connect to a Qlik
> Cloud tenant. On Qlik Cloud (your `go10njvx344b4j2.eu.qlikcloud.com`
> tenant) the successor feature is **Tabular Reporting** — same use case:
> pixel-perfect Excel reports, filtered per recipient, delivered by email on
> a schedule.

## Path A — your tenant (Qlik Cloud Tabular Reporting)

1. Build the **Libstar Product Analytics** app (load script + dashboard spec
   in this folder).
2. Install the **Qlik add-in for Microsoft Excel** (Office add-in; File >
   Get Add-ins > search "Qlik"). Sign in to the tenant.
3. Open `excel/Libstar_Product_Report.xlsx` (this repo) — it doubles as the
   report template: the named tables map 1:1 to app fields/measures:
   - `KPI_Summary`   ← master measures (Revenue 12m, Avg Margin %, SKUs…)
   - `Category_Perf` ← category × measures straight table
   - `Brand_Perf`    ← brand × measures straight table
   - `Province_Perf` ← province × measures straight table
   - `Data_Quality`  ← reject_reason table
   Use the add-in to re-bind each table to the app objects, then upload as a
   report template in the app (**Reporting** section > Create report).
4. Create a **report task**: schedule (e.g. Monday 07:00 SAST), recipients,
   optional section access/filters per recipient (e.g. one brand manager per
   brand via a `brand` filter).
5. Delivery lands in recipients' inboxes as filtered Excel — the NPrinting
   experience, cloud-native.

## Path B — client-managed NPrinting (if you demo on Windows Qlik Sense)

- Architecture: NPrinting Server (scheduler + web console) + NPrinting
  Designer (template editor) + a Qlik Sense Enterprise on Windows site.
- Connection: NPrinting connects with the Sense certificate; create a
  connection per app.
- Templates: Excel/Word/PowerPoint/PixelPerfect. The same named-table layout
  in `excel/Libstar_Product_Report.xlsx` ports directly into an NPrinting
  Excel template (drag the same fields/measures into the tags).
- Tasks: publish task → distribution list (users/groups) → email/NewsStand.
- Filters: per-user filters (e.g. `province = {'Western Cape'}`) replicate
  the Tabular Reporting per-recipient behaviour.

## What this repo already gives you

- The Excel workbook is built from the **same Synapse views** the Qlik app
  loads, so template numbers reconcile with the dashboard by construction.
- `rpt.vw_*` views are the single semantic layer — NPrinting/Tabular
  Reporting, the ebook and the Excel report all inherit one set of
  definitions.
