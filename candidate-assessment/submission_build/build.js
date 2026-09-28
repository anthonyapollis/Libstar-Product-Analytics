const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  ImageRun, PageBreak, TableOfContents, LevelFormat, PageOrientation,
  VerticalAlign, Header, Footer, PageNumber, ExternalHyperlink,
} = require("docx");

const BASE = "/home/user/Libstar-Product-Analytics/candidate-assessment";
const NAVY = "1F3864";
const TEAL = "0E7C7B";
const GREY = "595959";
const LIGHT = "EEF3F8";

// PNG IHDR chunk: width/height are the 4-byte big-endian ints at offset 16/20.
function pngSize(buf) {
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}
function img(path, widthPx) {
  const buf = fs.readFileSync(path);
  const { width, height } = pngSize(buf);
  const scale = widthPx / width;
  return new ImageRun({
    data: buf,
    type: "png",
    transformation: { width: widthPx, height: Math.round(height * scale) },
  });
}

function h1(text, opts = {}) {
  return new Paragraph({
    text, heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 200 },
    pageBreakBefore: opts.pageBreakBefore || false,
  });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, keepNext: true, keepLines: true, spacing: { before: 300, after: 150 } });
}
function h3(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_3, keepNext: true, keepLines: true, spacing: { before: 200, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, ...opts })],
    spacing: { after: 160 },
  });
}
function pMixed(runs, opts = {}) {
  return new Paragraph({ children: runs, spacing: { after: 160 }, ...opts });
}
function bullet(text, level = 0) {
  return new Paragraph({
    text,
    numbering: { reference: "bullets", level },
    spacing: { after: 80 },
  });
}
function caption(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, color: GREY, size: 20 })],
    spacing: { before: 80, after: 300 },
    alignment: AlignmentType.CENTER,
  });
}
function imgPara(path, widthPx, capText) {
  const children = [new Paragraph({ children: [img(path, widthPx)], alignment: AlignmentType.CENTER, spacing: { before: 200 } })];
  if (capText) children.push(caption(capText));
  return children;
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function cell(text, opts = {}) {
  const { bold = false, shade = null, width = 1000, align = AlignmentType.LEFT, color = null } = opts;
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold, size: 19, color: color || undefined })],
    })],
  });
}

function table(headers, rows, widths) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((hdr, i) => cell(hdr, { bold: true, shade: NAVY, width: widths[i], color: "FFFFFF" })),
  });
  const dataRows = rows.map((r, ri) => new TableRow({
    cantSplit: true,
    children: r.map((v, i) => cell(v, { width: widths[i], shade: ri % 2 === 1 ? LIGHT : null })),
  }));
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...dataRows],
  });
}

// ---------------------------------------------------------------------------
const sections1_content = [];

// TITLE PAGE
sections1_content.push(
  new Paragraph({ text: "", spacing: { before: 1600 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "JSB Data Engineer", bold: true, size: 30, color: GREY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 100 },
    children: [new TextRun({ text: "Practical Exercises — Candidate Submission", bold: true, size: 56, color: NAVY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 300, after: 800 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: TEAL, space: 8 } },
    children: [new TextRun({ text: "Payment reconciliation · Incremental API ingestion · Database design & reporting model", size: 24, color: TEAL })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 1200, after: 60 },
    children: [new TextRun({ text: "Tools used, end to end", bold: true, size: 22 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 400 },
    children: [new TextRun({ text: "MySQL 8.0 · MariaDB 10.11 (cross-verified) · Python 3.11 · dbt-core 1.7 (dbt-mysql) · Postman / Newman · Mermaid · Power BI (data model)", size: 20, color: GREY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 2000 },
    children: [new TextRun({ text: "Every number in this document was produced by actually running the code and queries shown — not hand-typed. Evidence for each figure lives in the accompanying repository.", italics: true, size: 20, color: GREY })],
  })
);

// HOW TO READ THIS
sections1_content.push(
  h1("How to read this document", { pageBreakBefore: true }),
  p("This document is the write-up for all three practical exercises. Each section states the scenario briefly, the approach taken, the tools used, and the evidence that it actually works — screenshots are captures of real runs, not mock-ups. Full source code, SQL, and raw evidence files accompany this document in the submitted repository (folder: candidate-assessment/)."),
  p("A short note on assumptions: per the brief's instruction not to stop on ambiguity, every assumption made is written down at the point it's used, not buried — for example the definition of NGR used in Exercise 3, and the fee-rounding tolerance used in Exercise 1."),
  h2("Contents"),
  bullet("Exercise 1 — Payment Gateway Reconciliation"),
  bullet("Exercise 2 — Incremental, Restartable API Ingestion"),
  bullet("Exercise 3 — Database Design: Players, Wallets, Bets, Bonuses"),
  bullet("Power BI — Reporting Data Model and Report")
);

module.exports = { sections1_content, h1, h2, h3, p, pMixed, bullet, caption, imgPara, pageBreak, cell, table, BASE, NAVY, TEAL, GREY, LIGHT };
