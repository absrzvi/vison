// One-page executive PoC timeline
// Run: node generate_timeline_onepager.js

const fs = require('fs');
const path = require('path');

const docxPath = path.join(process.env.APPDATA, 'npm', 'node_modules', 'docx');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  TabStopType, TabStopPosition,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber,
} = require(docxPath);

// brand palette (matches whitepaper)
const NAVY = "1F3A5F";
const ACCENT = "2E75B6";
const LIGHT = "EAF1F8";
const HEADER_FILL = "1F3A5F";
const AMBER = "C97A0B";
const GREEN = "2E7D32";

// US Letter
const PAGE_WIDTH = 12240;
const PAGE_HEIGHT = 15840;
const MARGIN = 1080; // 0.75" — tighter to fit one page
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN; // 10080

const tBorder = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const cellBorders = { top: tBorder, bottom: tBorder, left: tBorder, right: tBorder };

function gridTable(headers, rows, columnWidths, options = {}) {
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
        children: [
          new Paragraph({
            children: [new TextRun({ text: h, bold: true, color: "FFFFFF", size: 18 })],
          }),
        ],
      })
    ),
  });

  const dataRows = rows.map((row, ri) =>
    new TableRow({
      children: row.map((cell, ci) => {
        // cell can be a string OR { text, color, bold }
        const runs = Array.isArray(cell)
          ? cell.map(c => new TextRun({ text: c.text, color: c.color, bold: c.bold, size: 18 }))
          : [new TextRun({ text: String(cell), size: 18 })];
        return new TableCell({
          borders: cellBorders,
          width: { size: widths[ci], type: WidthType.DXA },
          shading: {
            fill: ri % 2 === 0 ? "FFFFFF" : LIGHT,
            type: ShadingType.CLEAR,
          },
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
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
    spacing: { before: 60, after: 120 },
  });

const small = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: 60 },
    children: [new TextRun({ text, size: 18, ...opts })],
  });

const bullet = (text) =>
  new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 40 },
    children: [new TextRun({ text, size: 18 })],
  });

// ---------- title ----------

const title = new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 60 },
  children: [
    new TextRun({ text: "Passenger Intelligence Service — PoC Timeline", bold: true, size: 32, color: NAVY }),
  ],
});

const subtitle = new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 120 },
  children: [
    new TextRun({ text: "3-month single-vehicle pilot · Single-page executive summary", italics: true, size: 20, color: "555555" }),
  ],
});

// ---------- at-a-glance strip ----------

const glance = gridTable(
  ["Duration", "Scope", "Decision gate", "Delivery model"],
  [[
    "12 weeks",
    "1 vehicle · 1 CCU · 6 onboard capabilities",
    "Pilot review at Week 12",
    "Managed SaaS, per-train monthly",
  ]],
  [2000, 4000, 2200, 1880]
);

// ---------- phase timeline (the centerpiece) ----------

const phases = gridTable(
  ["Phase", "Weeks", "Outcome", "Customer involvement"],
  [
    [
      [{ text: "1. Mobilisation", bold: true, color: NAVY }],
      "W1 – W2",
      "Contracts signed, vehicle identified, network access confirmed, onboard install scheduled.",
      "Sign-off on pilot vehicle and access windows.",
    ],
    [
      [{ text: "2. Install & Baseline", bold: true, color: NAVY }],
      "W3 – W4",
      "Hailo-8 M.2 installed in SYS2. Stack deployed. Cloud backend live. Baseline metrics (dwell time, congestion, manual occupancy checks) captured.",
      "1 access window for install. Operator data shadowing for baseline.",
    ],
    [
      [{ text: "3. Calibration", bold: true, color: NAVY }],
      "W5 – W6",
      "Camera tripwires tuned per coach. APC drift calibrated. Suppression rules signed off. False-positive rate driven below 5%.",
      "Operations sign-off on suppression-state transitions.",
    ],
    [
      [{ text: "4. Live Operation", bold: true, color: NAVY }],
      "W7 – W10",
      "Full service running in production traffic. Control Centre Dashboard adopted by operators. Conductor App in daily use. Weekly performance reports.",
      "Operator feedback loop. Incident logging shared.",
    ],
    [
      [{ text: "5. Pilot Review", bold: true, color: NAVY }],
      "W11 – W12",
      "Joint review of operational KPIs vs. baseline. Renewal / expansion decision. Fleet rollout plan tabled.",
      "Executive review meeting + decision.",
    ],
  ],
  [2200, 1300, 4400, 2180]
);

// ---------- milestones row ----------

const milestonesHeader = new Paragraph({
  spacing: { before: 180, after: 60 },
  children: [new TextRun({ text: "Key milestones", bold: true, size: 22, color: NAVY })],
});

const milestones = gridTable(
  ["Milestone", "Target", "Owner"],
  [
    ["M1 — Kickoff & access windows confirmed", "End W2", "Joint"],
    ["M2 — Onboard stack live, first events flowing", "End W4", "Nomad Digital"],
    ["M3 — Calibration accepted (accuracy ≥95%, FP <5%)", "End W6", "Joint"],
    ["M4 — Mid-pilot checkpoint (operational adoption review)", "End W8", "Joint"],
    ["M5 — Final KPI review & renewal decision", "End W12", "Joint"],
  ],
  [5800, 2200, 2080]
);

// ---------- success criteria + risks (two columns side by side) ----------

const sideHeader = new Paragraph({
  spacing: { before: 180, after: 60 },
  children: [new TextRun({ text: "What success looks like", bold: true, size: 22, color: NAVY })],
});

const twoCol = new Table({
  width: { size: CONTENT_WIDTH, type: WidthType.DXA },
  columnWidths: [Math.floor(CONTENT_WIDTH / 2), CONTENT_WIDTH - Math.floor(CONTENT_WIDTH / 2)],
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders: cellBorders,
          width: { size: Math.floor(CONTENT_WIDTH / 2), type: WidthType.DXA },
          shading: { fill: LIGHT, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 140, right: 140 },
          children: [
            new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Operational targets", bold: true, color: NAVY, size: 20 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Occupancy accuracy ≥ 95%", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "False-positive alert rate < 5%", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "System uptime ≥ 99.5%", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Alert latency within station dwell window", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Raw video confirmed never to leave train", size: 18 })] }),
          ],
        }),
        new TableCell({
          borders: cellBorders,
          width: { size: CONTENT_WIDTH - Math.floor(CONTENT_WIDTH / 2), type: WidthType.DXA },
          shading: { fill: "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 140, right: 140 },
          children: [
            new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Risk & mitigation", bold: true, color: NAVY, size: 20 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Access windows slip → install batched into next available depot slot; no schedule rebuild needed.", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Calibration takes longer than W5–W6 → Phase 4 starts in parallel under provisional thresholds.", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Connectivity gaps → onboard interfaces remain fully functional; cloud sync resumes idempotently.", size: 18 })] }),
            new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: "Stakeholder churn → weekly steering call keeps decision-makers aligned.", size: 18 })] }),
          ],
        }),
      ],
    }),
  ],
});

// ---------- footer info ----------

const decisionRow = new Paragraph({
  spacing: { before: 180, after: 0 },
  alignment: AlignmentType.LEFT,
  children: [
    new TextRun({ text: "Decision at Week 12: ", bold: true, color: NAVY, size: 20 }),
    new TextRun({ text: "Renewal at scale · Fleet rollout plan · Commercial terms confirmed", size: 20 }),
  ],
});

const contact = new Paragraph({
  spacing: { before: 60, after: 0 },
  alignment: AlignmentType.LEFT,
  children: [
    new TextRun({ text: "Contact: ", bold: true, size: 18, color: "555555" }),
    new TextRun({ text: "abbas.rizvi@nomadrail.com  ·  Nomad Digital  ·  Passenger Intelligence Service", size: 18, color: "555555" }),
  ],
});

// ---------- assemble ----------

const doc = new Document({
  creator: "Nomad Digital",
  title: "Passenger Intelligence Service — PoC Timeline",
  description: "One-page executive timeline for the 3-month PoC.",
  styles: {
    default: { document: { run: { font: "Calibri", size: 20 } } },
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
                new TextRun({ text: "Nomad Digital — Confidential  ·  PoC Timeline v1.0", size: 16, color: "888888" }),
              ],
            }),
          ],
        }),
      },
      children: [
        title,
        subtitle,
        hr(),
        glance,
        new Paragraph({
          spacing: { before: 180, after: 60 },
          children: [new TextRun({ text: "Phase timeline (12 weeks from [Start Date])", bold: true, size: 22, color: NAVY })],
        }),
        phases,
        milestonesHeader,
        milestones,
        sideHeader,
        twoCol,
        decisionRow,
        contact,
      ],
    },
  ],
});

const outPath = path.resolve(__dirname, "..", "..", "Passenger-Intelligence-Service-PoC-Timeline.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outPath, buffer);
  console.log("Wrote:", outPath, "(" + buffer.length + " bytes)");
});
