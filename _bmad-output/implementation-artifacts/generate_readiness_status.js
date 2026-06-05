// One-page internal readiness status — pre-install gate chart
// Run: node generate_readiness_status.js

const fs = require('fs');
const path = require('path');

const docxPath = path.join(process.env.APPDATA, 'npm', 'node_modules', 'docx');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
} = require(docxPath);

// brand palette
const NAVY = "1F3A5F";
const ACCENT = "2E75B6";
const LIGHT = "EAF1F8";
const HEADER_FILL = "1F3A5F";
const GREEN = "2E7D32";
const AMBER = "C97A0B";
const RED = "B23A3A";
const GREY = "777777";

// US Letter, tight margins for one page
const PAGE_WIDTH = 12240;
const PAGE_HEIGHT = 15840;
const MARGIN = 1000; // ~0.7"
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN; // 10240

const tBorder = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const cellBorders = { top: tBorder, bottom: tBorder, left: tBorder, right: tBorder };

// status pill helper
function statusPill(text, color) {
  return new TextRun({
    text: ` ${text} `,
    bold: true,
    color: "FFFFFF",
    size: 16,
    shading: { fill: color, type: ShadingType.CLEAR },
  });
}

function gridTable(headers, rows, columnWidths) {
  const widths = columnWidths.slice();
  const sum = widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += CONTENT_WIDTH - sum;

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      new TableCell({
        borders: cellBorders,
        width: { size: widths[i], type: WidthType.DXA },
        shading: { fill: HEADER_FILL, type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: "FFFFFF", size: 17 })] })],
      })
    ),
  });

  const dataRows = rows.map((row, ri) =>
    new TableRow({
      children: row.map((cell, ci) => {
        // cell can be array of TextRun
        const runs = Array.isArray(cell)
          ? cell
          : [new TextRun({ text: String(cell), size: 17 })];
        return new TableCell({
          borders: cellBorders,
          width: { size: widths[ci], type: WidthType.DXA },
          shading: {
            fill: ri % 2 === 0 ? "FFFFFF" : LIGHT,
            type: ShadingType.CLEAR,
          },
          margins: { top: 50, bottom: 50, left: 100, right: 100 },
          children: [new Paragraph({ children: runs })],
        });
      }),
    })
  );

  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...dataRows],
  });
}

const hr = () =>
  new Paragraph({
    children: [new TextRun({ text: "" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 1 } },
    spacing: { before: 40, after: 100 },
  });

// ---------- title ----------

const title = new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 40 },
  children: [
    new TextRun({ text: "Pre-Install Readiness Status", bold: true, size: 30, color: NAVY }),
  ],
});

const subtitle = new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 80 },
  children: [
    new TextRun({ text: "Internal · As of 2026-05-28 · Owner: Abbas Rizvi", italics: true, size: 18, color: GREY }),
  ],
});

// ---------- headline ----------

const headlineTable = new Table({
  width: { size: CONTENT_WIDTH, type: WidthType.DXA },
  columnWidths: [CONTENT_WIDTH],
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders: cellBorders,
          width: { size: CONTENT_WIDTH, type: WidthType.DXA },
          shading: { fill: LIGHT, type: ShadingType.CLEAR },
          margins: { top: 100, bottom: 100, left: 160, right: 160 },
          children: [
            new Paragraph({
              children: [
                new TextRun({ text: "HEADLINE  ", bold: true, color: NAVY, size: 18 }),
                new TextRun({ text: "Phase 1 PoC code-complete. ", bold: true, size: 18 }),
                new TextRun({ text: "~4 weeks of pre-install work remains. Critical path is the hardening sprint; the three external dependencies must move in parallel.", size: 18 }),
              ],
            }),
          ],
        }),
      ],
    }),
  ],
});

// ---------- delivered ----------

const deliveredHdr = new Paragraph({
  spacing: { before: 140, after: 40 },
  children: [new TextRun({ text: "What's delivered", bold: true, size: 20, color: NAVY })],
});

const delivered = gridTable(
  ["Workstream", "Scope", "Status", "Quality"],
  [
    [
      "Epic 1 — Foundation & Shared Infra",
      "Event envelope, EventType taxonomy, Postgres schema, SQLite sync cursor, APCAdapter Protocol, WS subscription, REST skeleton",
      [statusPill("DONE", GREEN)],
      "≥80% cov, mypy --strict",
    ],
    [
      "Epic 2 — CC Dashboard Live Ops",
      "Real WS client, KPI strip, fleet list, unified feed, escalation detail, train detail, skeletons, configurable thresholds",
      [statusPill("DONE", GREEN)],
      "All ACs met",
    ],
    [
      "Epic 3 — CC Analytics & Sys Health",
      "Analytics REST, exception workflow, occupancy heatmap, dwell time, AI detection quality, system health, maintenance ticket API",
      [statusPill("DONE", GREEN)],
      "All ACs met",
    ],
    [
      "Epic 4 — Onboard Edge Pipeline",
      "11 stories + cloud-sync. VLAN pollers, rtsp-ingest, inference (Hailo), fusion (alerts, ledger, comfort), event-store, cloud sync",
      [statusPill("DONE", GREEN)],
      "174 review patches, ≥94% cov",
    ],
    [
      "Epic 5 — Luggage Monitoring",
      "WS live feed, live UI, KPI live monitoring, ISO timestamps",
      [statusPill("DONE", GREEN)],
      "All ACs met",
    ],
    [
      "Epic 1.5 — Onboard Containerisation",
      "inference + rtsp-ingest Dockerfiles, docker-compose.onboard.yml, end-to-end smoke test",
      [statusPill("DONE", GREEN)],
      "Smoke test green",
    ],
  ],
  [2700, 4900, 1100, 1540]
);

// ---------- remaining engineering ----------

const remainingHdr = new Paragraph({
  spacing: { before: 140, after: 40 },
  children: [new TextRun({ text: "Remaining engineering (critical path)", bold: true, size: 20, color: NAVY })],
});

const remaining = gridTable(
  ["Epic / item", "Scope", "Effort", "Status"],
  [
    [
      "Epic 6 — Fusion Hardening",
      "Journey-lifecycle reset, async exception hardening, AsyncMock test hygiene (3 stories)",
      "~3 days",
      [statusPill("READY", AMBER)],
    ],
    [
      "Epic 7 — Retry & Idempotency",
      "4xx retry exclusion, gangway tripwire emit-then-commit (2 stories)",
      "~2 days",
      [statusPill("READY", AMBER)],
    ],
    [
      "Epic 8 — Analytics UI Hardening",
      "AbortController pass, FleetContext memoisation (2 stories)",
      "~2 days",
      [statusPill("READY", AMBER)],
    ],
    [
      "Epic 9 — Container & Infra Hardening",
      "Postgres analytics indexes, Dockerfile HEALTHCHECK + non-editable, batch commits (3 stories)",
      "~3 days",
      [statusPill("READY", AMBER)],
    ],
    [
      "Process — ADR-17 update + deferred-work triage",
      "Update ADR-17 (D5 rename, per-coach shape). Triage deferred-work.md before next planning. Carry-overs from E4 phase-2 retro.",
      "~0.5 day",
      [statusPill("READY", AMBER)],
    ],
    [
      "Hardware bring-up smoothing buffer",
      "First real SYS2 contact: group_add for Hailo PCIe, service_healthy gates, 25–30 camera TOPS validation, PWA offline check",
      "~5 days",
      [statusPill("RESERVED", GREY)],
    ],
  ],
  [2700, 4900, 900, 1740]
);

// ---------- external dependency gate chart ----------

const depsHdr = new Paragraph({
  spacing: { before: 140, after: 40 },
  children: [new TextRun({ text: "External dependency gates", bold: true, size: 20, color: NAVY })],
});

const deps = gridTable(
  ["Dependency", "Owner", "Blocks", "Risk", "Mitigation"],
  [
    [
      [new TextRun({ text: "Hailo digest pin", bold: true, size: 17 })],
      "Hailo Developer Zone access",
      "Reproducible production image (inference, rtsp-ingest)",
      [statusPill("LOW", GREEN)],
      "Tag 4.23 in place; one-line swap once digest is known. Does not block install.",
    ],
    [
      [new TextRun({ text: "APC wire format", bold: true, size: 17 })],
      "AFZ supplier (via OEBB)",
      "Live occupancy calibration vs. APC ground truth",
      [statusPill("MED", AMBER)],
      "MockAPCAdapter ships now; ADR-15 makes camera primary so calibration drift, not function, is what's gated. Install can proceed; Baseline accuracy may be provisional until adapter swap.",
    ],
    [
      [new TextRun({ text: "Stadler MIB alarm list", bold: true, size: 17 })],
      "Stadler (STADLER-IM-MIB_Configuration.xlsm)",
      "TCMS plain-language alarm surfacing (FR6)",
      [statusPill("MED", AMBER)],
      "vlan-pollers ships with placeholder schema; alarm surfacing degrades to coded values until populated. Install can proceed.",
    ],
    [
      [new TextRun({ text: "Real cameras.json polygons", bold: true, size: 17 })],
      "Ops/UX session per coach type",
      "Vestibule congestion accuracy, seated/standing split, gangway tripwires",
      [statusPill("MED", AMBER)],
      "Placeholders cover full-frame today; tuning happens during the calibration phase (W5–W6 of PoC). Install can proceed.",
    ],
    [
      [new TextRun({ text: "SYS2 access window", bold: true, size: 17 })],
      "OEBB depot scheduling",
      "Hardware install itself",
      [statusPill("HIGH", RED)],
      "No mitigation — this IS the install. Lock the depot slot now; everything else is sequenced around it.",
    ],
  ],
  [1700, 1800, 2300, 700, CONTENT_WIDTH - 6500]
);

// ---------- timing rollup ----------

const timingHdr = new Paragraph({
  spacing: { before: 140, after: 40 },
  children: [new TextRun({ text: "Timing rollup", bold: true, size: 20, color: NAVY })],
});

const timing = gridTable(
  ["Track", "Elapsed estimate", "Notes"],
  [
    ["Hardening sprint 1 (Epics 6–9)", "10 working days (2 weeks)", "Mechanical, well-scoped. Phase-2 cadence supports this estimate."],
    ["External dependencies in parallel", "1–2 weeks elapsed", "Hailo digest + APC format + Stadler MIB + polygon session. None on the critical path."],
    ["Hardware bring-up buffer", "~1 week", "First-contact integration smoothing on real SYS2."],
    [
      [new TextRun({ text: "Total to Install & Baseline ready", bold: true, size: 17 })],
      [new TextRun({ text: "~4 weeks from 2026-05-28", bold: true, size: 17 })],
      [new TextRun({ text: "Target: install window can open mid-to-late June 2026.", bold: true, size: 17 })],
    ],
  ],
  [3400, 2600, CONTENT_WIDTH - 6000]
);

// ---------- assemble ----------

const doc = new Document({
  creator: "Nomad Digital",
  title: "Passenger Intelligence Service — Pre-Install Readiness Status",
  description: "Internal one-pager: app development status and external dependency gates ahead of PoC Install & Baseline.",
  styles: {
    default: { document: { run: { font: "Calibri", size: 18 } } },
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 360, hanging: 220 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Nomad Digital — Internal  ·  Pre-Install Readiness v1.0  ·  Snapshot 2026-05-28", size: 14, color: "888888" }),
              ],
            }),
          ],
        }),
      },
      children: [
        title,
        subtitle,
        hr(),
        headlineTable,
        deliveredHdr,
        delivered,
        remainingHdr,
        remaining,
        depsHdr,
        deps,
        timingHdr,
        timing,
      ],
    },
  ],
});

const outPath = path.resolve(__dirname, "..", "..", "Passenger-Intelligence-Service-Readiness-Status.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outPath, buffer);
  console.log("Wrote:", outPath, "(" + buffer.length + " bytes)");
});
