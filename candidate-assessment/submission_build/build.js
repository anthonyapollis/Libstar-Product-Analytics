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

// Numbered headings. Every numbered h1/h2 is recorded in HEADINGS so the contents page and the
// requirements index can quote its number (and, after the first render, its page).
const HEADINGS = [];
let n1 = 0, n2 = 0;
function h1(text, opts = {}) {
  let label = text;
  if (opts.num) {
    n1 += 1; n2 = 0;
    label = `${n1}. ${text}`;
    HEADINGS.push({ level: 1, num: String(n1), title: text, label, key: opts.key || String(n1) });
  } else if (opts.appendix) {
    label = `Appendix ${opts.appendix}. ${text}`;
    HEADINGS.push({ level: 1, num: opts.appendix, title: text, label, key: opts.key || `app${opts.appendix}` });
  }
  return new Paragraph({
    text: label, heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 200 },
    pageBreakBefore: opts.pageBreakBefore || false,
  });
}
function h2(text, opts = {}) {
  let label = text;
  if (n1 > 0 && !opts.plain) {
    n2 += 1;
    label = `${n1}.${n2} ${text}`;
    HEADINGS.push({ level: 2, num: `${n1}.${n2}`, title: text, label, key: opts.key || `${n1}.${n2}` });
  }
  return new Paragraph({ text: label, heading: HeadingLevel.HEADING_2, keepNext: true, keepLines: true,
                         pageBreakBefore: opts.pageBreakBefore || false, spacing: { before: 300, after: 150 } });
}
function h3(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_3, keepNext: true, keepLines: true, spacing: { before: 200, after: 100 } });
}
// "Answers: …" tag under a section heading: which part of the brief this section answers.
function answers(text) {
  return new Paragraph({
    keepNext: true,
    shading: { type: ShadingType.CLEAR, fill: LIGHT },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: TEAL, space: 6 } },
    spacing: { before: 0, after: 160 },
    indent: { left: 120 },
    children: [new TextRun({ text: "Answers  ", bold: true, size: 18, color: TEAL }),
               new TextRun({ text, size: 18, color: GREY })],
  });
}
// Shaded "In brief" box at the start of an exercise: the short written summary the brief asks for.
function summaryBox(title, lines) {
  const cellChildren = [new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 21, color: NAVY })], spacing: { after: 80 } }),
    ...lines.map((l) => new Paragraph({ children: [new TextRun({ text: l, size: 19 })], numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 } }))];
  return new Table({
    width: { size: 9360, type: WidthType.DXA }, columnWidths: [9360],
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 9360, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: LIGHT },
      margins: { top: 120, bottom: 120, left: 180, right: 180 },
      borders: { top: { style: BorderStyle.SINGLE, size: 8, color: TEAL }, bottom: { style: BorderStyle.SINGLE, size: 8, color: TEAL },
                 left: { style: BorderStyle.SINGLE, size: 8, color: TEAL }, right: { style: BorderStyle.SINGLE, size: 8, color: TEAL } },
      children: cellChildren,
    })] })],
  });
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
  const children = [new Paragraph({ children: [img(path, widthPx)], alignment: AlignmentType.CENTER, keepNext: !!capText, spacing: { before: 200 } })];
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
    children: [new TextRun({ text: "MariaDB 10.11 and MariaDB 10.4 (XAMPP), MySQL-compatible · Python 3.11 · dbt-core 1.7 (dbt-mysql) · Postman / Newman · Mermaid · Power BI (data model) · Databricks (Delta Lake, serverless)", size: 20, color: GREY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: "AI coding assistants (Claude Code and Codex) were used during development and review. The submitted code and results were executed and checked, including on my own Windows PC, and I can explain the design decisions.", size: 20, color: GREY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 1400 },
    children: [new TextRun({ text: "Every number in this document was produced by actually running the code and queries shown — not hand-typed. Evidence for each figure lives in the accompanying repository.", italics: true, size: 20, color: GREY })],
  })
);

module.exports = { sections1_content, HEADINGS, h1, h2, h3, answers, summaryBox, p, pMixed, bullet, caption, imgPara, pageBreak, cell, table, BASE, NAVY, TEAL, GREY, LIGHT };
