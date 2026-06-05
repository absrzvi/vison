import {
  Document, Packer, Paragraph, TextRun, ImageRun, HeadingLevel,
  AlignmentType, PageBreak, LevelFormat, BorderStyle, PageNumber,
  Header, Footer, TableOfContents,
} from 'docx';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const IMG_DIR = resolve(__dirname, 'images');
const OUT = resolve(__dirname, 'OEBB-Passenger-Intelligence-User-Manual.docx');

// Screenshots are 1440x900. Page content width on US Letter w/ 1" margins is 6.5".
// 6.5" * 96dpi = 624px for ImageRun. Preserve aspect: 624 / 1440 * 900 = 390.
const IMG_W = 624;
const IMG_H = 390;

const img = (name) => new ImageRun({
  type: 'png',
  data: readFileSync(resolve(IMG_DIR, name)),
  transformation: { width: IMG_W, height: IMG_H },
  altText: { title: name, description: name, name },
});

const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
const h3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
const p = (text) => new Paragraph({ children: [new TextRun(text)] });
const caption = (text) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 60, after: 240 },
  children: [new TextRun({ text, italics: true, size: 20, color: '666666' })],
});
const screenshot = (file) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 60 },
  children: [img(file)],
});
const bullet = (text) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  children: [new TextRun(text)],
});
const bulletBold = (label, text) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  children: [
    new TextRun({ text: label, bold: true }),
    new TextRun({ text: ' — ' + text }),
  ],
});
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

const children = [
  // Cover
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 2400, after: 240 },
    children: [new TextRun({ text: 'ÖBB Passenger Intelligence', bold: true, size: 56, color: 'C8102E' })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [new TextRun({ text: 'Control Centre — Walkthrough Guide', size: 36 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 2400 },
    children: [new TextRun({ text: 'Internal demo edition · May 2026', size: 22, color: '666666', italics: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'Nomad Digital · OEBB Smart Rail PoC', size: 22 })],
  }),
  pageBreak(),

  // Introduction
  h1('1. Introduction'),
  p('This document is a guided walkthrough of the Control Centre dashboard — the landside operator-facing surface of the ÖBB Passenger Intelligence platform. It is intended for internal stakeholders, demo audiences, and reviewers who want to understand what each screen does and what value it provides without operating it directly.'),
  p('Each section covers one tab of the dashboard, with a screenshot, an explanation of the layout, and a note on what the screen demonstrates from a product standpoint.'),

  h2('1.1 What is the Control Centre?'),
  p('The Control Centre is the landside web application used by ÖBB operators to monitor the live fleet, triage AI-generated alerts from on-train cameras and sensors, and coordinate response with onboard staff (Conductor App) and field technicians (Maintenance App).'),
  p('All raw video stays on the train (Hailo-8 edge inference on the R5001C SYS2 unit). Only structured events — occupancy estimates, alert metadata, dwell-time signals, system health — are pushed to the cloud-backend over the train-to-ground link. The Control Centre consumes those events through a REST + SSE API and renders them as the live operations picture.'),

  h2('1.2 Scope of this guide'),
  p('This edition covers four tabs that are fully populated in the current PoC build:'),
  bulletBold('Live', 'fleet overview, map, and active escalations.'),
  bulletBold('Escalations', 'full incident triage list with filters and acknowledgement.'),
  bulletBold('Occupancy', 'per-train and per-coach passenger density.'),
  bulletBold('Luggage', 'unattended-bag and overcrowded-luggage-area events.'),
  p('The remaining two tabs — System Health and Analytics — render historical and telemetry data that depends on a longer event-store warm-up than the demo environment provides. They will be documented in a follow-up edition once the backend is seeded with representative event volume.'),
  pageBreak(),

  // Layout primer
  h1('2. Common layout'),
  p('Every tab shares the same chrome:'),
  bulletBold('Header (top)', 'ÖBB wordmark, application title, the unacknowledged-critical badge, an operator preferences gear, and the operating context tag (CONTROL CENTRE).'),
  bulletBold('Tab bar', 'Live · Escalations · Occupancy · Luggage · System Health · Analytics. The number badge next to "Live" reflects the current unacknowledged escalation count fleet-wide.'),
  bulletBold('KPI strip', 'a row of summary tiles directly under the tab bar. The tiles change per tab and double as quick filters where applicable.'),
  bulletBold('Main work area', 'tab-specific content. Wherever a fleet list and a detail view both appear, the list is on the left and the detail context is on the right.'),
  p('The UI is dark-themed by default to suit a 24/7 operations environment. Severity is colour-coded consistently across the application: red for critical, amber for warning, green for normal.'),
  pageBreak(),

  // Live tab
  h1('3. Live'),
  p('The default landing screen. The Live tab gives an operator the entire fleet picture in a single view: which trains are running, where they are geographically, which ones need attention, and what is currently being escalated.'),
  screenshot('01-live.png'),
  caption('Figure 1 — Live tab with the fleet list (left), the Austria fleet map (centre), an inspected train detail (centre-bottom), and the live escalations feed (right).'),

  h2('3.1 KPI strip'),
  p('From left to right, the tiles surface the headline operating numbers:'),
  bulletBold('Active Trains', 'number of vehicles currently reporting telemetry.'),
  bulletBold('Open Escalations', 'unresolved incidents fleet-wide. Clickable — jumps to the Escalations tab pre-filtered to open items.'),
  bulletBold('Active Incidents', 'subset of escalations that are AI-driven incidents (door obstructions, overcrowding, safety events).'),
  bulletBold('Capacity Alerts', 'occupancy threshold breaches awaiting review.'),
  bulletBold('Luggage Alerts', 'unattended-bag and overcrowded-rack events.'),
  bulletBold('Live · Last Update', 'data freshness indicator. Turns amber if the SSE stream stalls and red if the connection drops.'),

  h2('3.2 Fleet list'),
  p('The left rail lists trains ranked by current concern, not by ID. Each row shows the train number, its route, a coach-occupancy mini-strip (one block per coach, severity-coloured), and an averaged occupancy figure. A small inline tag like "Dwelling · Bruck an der Mur · +4 min" appears when the AI has flagged that this train is currently misbehaving against schedule.'),
  p('Operators can toggle the strip between a Passengers view (occupancy density) and a Severity view (escalation hotness) using the segmented control above the list. A "Show N normal trains" button at the bottom collapses healthy stock out of view.'),

  h2('3.3 Fleet map'),
  p('A geographic view of Austria with one pin per train, coloured by current severity. The legend in the upper-right confirms the colour mapping. The map is interactive: clicking a pin selects that train and opens the detail panel below.'),

  h2('3.4 Train detail panel'),
  p('When a train is selected, the centre-bottom panel exposes coach-level detail: occupancy percentage per coach, with the worst-performing coach outlined. An "Active Alerts" sub-panel lists any open AI alerts attached to that specific train.'),

  h2('3.5 Escalations feed'),
  p('The right-hand rail is the live escalations stream, identical in semantics to the dedicated Escalations tab but constrained to the most recent items. Each card identifies the source channel (AI, Occupancy, Conrad, Roland — the onboard messaging gateways), the affected train and coach, a one-line description, confidence (where applicable), and an Acknowledge action.'),
  pageBreak(),

  // Escalations tab
  h1('4. Escalations'),
  p('The Escalations tab is the operator queue. It is the screen an operator lives on during a shift: every alert that needs human acknowledgement, with filters and a clear acknowledge action.'),
  screenshot('02-escalations.png'),
  caption('Figure 2 — Escalations tab with the queue summary KPIs (top), filter chips, and the prioritised escalation list.'),

  h2('4.1 KPI strip'),
  p('Four queue-state counters:'),
  bulletBold('Unacknowledged', 'red — the operator’s primary action queue.'),
  bulletBold('Acknowledged / Open', 'amber — picked up but not yet resolved.'),
  bulletBold('Resolved this session', 'green — closed during the current shift.'),
  bulletBold('Total active', 'all escalations not yet archived.'),

  h2('4.2 Filter chips'),
  p('The chip bar above the list lets the operator narrow the queue by source (AI, Occupancy, Luggage, Staff, Roland), by state (Unacknowledged, Acknowledged, Resolved), and by severity (Critical, Warning, Info). Chip combinations are additive.'),

  h2('4.3 Escalation cards'),
  p('Each row is one escalation. The card shows:'),
  bullet('A source tag — the channel the escalation came from (AI inference, Occupancy threshold, Conrad onboard, Roland technical messaging).'),
  bullet('A short title describing what happened — for example "Door obstruction — Coach C3".'),
  bullet('A one-line body with context — sensor description, confidence percentage, location.'),
  bullet('The affected train and coach, presented as clickable chips that jump into the train detail.'),
  bullet('A current state label (UNACKNOWLEDGED / ACKNOWLEDGED) and a timestamp.'),
  bullet('An Acknowledge button for items that still need operator pickup.'),
  p('AI-driven escalations always carry a confidence percentage so the operator can weigh model certainty against context (for example a 96 % door-obstruction event is treated very differently from a 71 % overcrowding warning).'),
  pageBreak(),

  // Occupancy tab
  h1('5. Occupancy'),
  p('The Occupancy tab is the dedicated passenger-density view. It answers: which train is fullest, which coach inside that train is fullest, and where inside the coach passengers are concentrated.'),
  screenshot('03-occupancy.png'),
  caption('Figure 3 — Occupancy tab with the fleet list (left), per-coach density heat-blocks (centre), seat-level map (bottom-left), and per-coach metrics (bottom-right).'),

  h2('5.1 KPI strip'),
  bulletBold('Active Trains', 'as on the Live tab.'),
  bulletBold('Fleet avg occupancy', 'fleet-wide passenger density, rolling average.'),
  bulletBold('Over 75 % threshold', 'count of trains exceeding the configurable alert threshold.'),
  bulletBold('Peak train', 'the single train currently driving the highest density.'),
  bulletBold('Live · Last update', 'freshness indicator.'),

  h2('5.2 Fleet list (left)'),
  p('Trains ranked by occupancy descending. Each row shows the headline percentage, the coach-strip, the count of coaches over threshold (for example "4/8"), and a status tag where the AI has identified a contributing condition such as "Dwell" or "Boarding".'),

  h2('5.3 Selected train view'),
  p('Selecting a train opens a three-band view of that train:'),
  bullet('A schedule banner — current schedule deviation in minutes, dwell status, platform-side context (for example "high crowding").'),
  bullet('A coach occupancy strip — one tile per coach (C1–C8), tile colour driven by density, with the percentage stamped on the tile. Selected coach is outlined.'),
  bullet('A coach-aggregate row — peak coach, count over threshold, and the train’s rank in the fleet.'),

  h2('5.4 Per-coach detail (bottom)'),
  p('The bottom half drills into the selected coach:'),
  bulletBold('Seat map', 'a schematic of seat blocks coloured FREE / LIMITED / FULL. This is derived from CCTV-based inference, not from booking data.'),
  bulletBold('Metrics tile', 'head count, seated vs standing split, vestibule temperature, luggage-rack utilisation, and whether dwell-time degradation is currently being attributed to this coach.'),
  bulletBold('Door congestion bar', 'a percentage indicator of how blocked the doorway zone is — feeds the AI dwell-prediction model.'),
  bulletBold('Alert threshold slider', 'operator-tunable threshold (default 75 %) used to drive the over-threshold counters.'),
  pageBreak(),

  // Luggage tab
  h1('6. Luggage'),
  p('The Luggage tab surfaces two distinct event categories that come from luggage-rack and floor-area vision models: bags left unattended for longer than the configured window, and luggage areas that have exceeded capacity.'),
  screenshot('04-luggage.png'),
  caption('Figure 4 — Luggage tab with the event KPI summary and the per-train, per-event detail list.'),

  h2('6.1 KPI strip'),
  bulletBold('Longest unattended', 'duration of the longest still-open unattended-bag event.'),
  bulletBold('Longest active', 'duration of the longest still-active overcrowding event.'),
  bulletBold('Unattended alerts', 'open unattended-bag count.'),
  bulletBold('Overcrowded areas', 'open rack-overflow count.'),
  bulletBold('Oversized items', 'count of oversized-item detections currently flagged.'),
  bulletBold('Cleared / resolved', 'closed within the session.'),

  h2('6.2 Filter chips'),
  p('The chips immediately above the list filter by event type: All, Unattended, Overcrowded, Oversized, Resolved.'),

  h2('6.3 Event groups'),
  p('Events are grouped by train. Each train group shows the train number, an event count, and the destination station. Inside each group, individual events expose:'),
  bullet('The event type tag — UNATTENDED, OVERCROWDED, or OVERSIZED.'),
  bullet('A short headline with the coach and zone — for example "Unattended bag — C4 seating-mid".'),
  bullet('A one-line body — for unattended events, how long the bag has been unattended and the track reference; for overcrowded events, the rack ID and detected item count.'),
  bullet('A confidence percentage and event age, top-right.'),
  bullet('A "Train detail" deep-link and an Ack button.'),
  pageBreak(),

  // Closing
  h1('7. Not yet covered'),
  p('Two tabs are intentionally omitted from this edition:'),
  bulletBold('System Health', 'shows per-train edge-device telemetry (Hailo utilisation, camera-feed health, VLAN-poller status, sync-cursor lag). Requires the cloud-backend to be receiving live telemetry from a connected edge deployment; the demo environment does not yet seed it.'),
  bulletBold('Analytics', 'historical views (capacity exceptions, occupancy heatmap, dwell-time, AI detection quality) over 7/14/30-day windows. Requires accumulated event history; will be documented once representative volume is available.'),
  p('These tabs will be added in a follow-up revision of this manual once the backing data is in place.'),

  h1('8. Demo notes'),
  p('A few things worth flagging if you are running this dashboard in front of an audience:'),
  bullet('All data shown in this edition is synthetic. The fleet, occupancy figures, escalations, and luggage events are generated by the in-app mock client so the UI can be reviewed without a live edge feed.'),
  bullet('The Live tab’s "Reconnecting…" banner is the SSE-stream status indicator. In the mock-data demo configuration it does not appear; in the wired configuration it will flicker briefly during the initial connection handshake.'),
  bullet('The screenshots in this document were taken at a 1440-pixel-wide viewport. On smaller screens the layout reflows — the fleet rail collapses first.'),
  bullet('The "3 critical" badge in the top-right header is sourced from the same unacknowledged-critical count that drives the Live tab badge, so the two will always agree.'),
];

const doc = new Document({
  creator: 'OEBB Smart Rail PoC',
  title: 'OEBB Passenger Intelligence — Control Centre Walkthrough',
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: 'C8102E' },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: '222222' },
        paragraph: { spacing: { before: 240, after: 140 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: '444444' },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'C8102E', space: 4 } },
          children: [new TextRun({ text: 'ÖBB Passenger Intelligence · Control Centre Walkthrough', size: 18, color: '666666' })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: 'Page ', size: 18, color: '666666' }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '666666' }),
          ],
        })],
      }),
    },
    children,
  }],
});

const buffer = await Packer.toBuffer(doc);
writeFileSync(OUT, buffer);
console.log('Wrote', OUT, '(' + (buffer.length / 1024).toFixed(1) + ' KB)');
