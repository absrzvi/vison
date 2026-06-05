// Generate the Passenger Intelligence Service technical whitepaper
// Run: node generate_whitepaper.js

const fs = require('fs');
const path = require('path');

const docxPath = path.join(process.env.APPDATA, 'npm', 'node_modules', 'docx');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  TabStopType, TabStopPosition,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak,
} = require(docxPath);

// ---------- helpers ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };

const NAVY = "1F3A5F";
const ACCENT = "2E75B6";
const LIGHT = "EAF1F8";
const HEADER_FILL = "1F3A5F";

const PAGE_WIDTH = 12240;
const MARGIN = 1440;
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN; // 9360

// shorthand paragraph helpers
const p = (text, opts = {}) =>
  new Paragraph({
    children: [new TextRun({ text, ...(opts.run || {}) })],
    spacing: opts.spacing || { after: 120 },
    ...opts.paragraph,
  });

const h1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text })],
  });

const h2 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text })],
  });

const h3 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text })],
  });

const bullet = (text, level = 0) =>
  new Paragraph({
    numbering: { reference: "bullets", level },
    children: [new TextRun({ text })],
  });

const bulletRich = (runs, level = 0) =>
  new Paragraph({
    numbering: { reference: "bullets", level },
    children: runs,
  });

const numbered = (text) =>
  new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    children: [new TextRun({ text })],
  });

// Build a two-column table (label, value)
function kvTable(rows) {
  const colA = 3120;
  const colB = CONTENT_WIDTH - colA;
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: [colA, colB],
    rows: rows.map(([k, v], i) =>
      new TableRow({
        children: [
          new TableCell({
            borders,
            width: { size: colA, type: WidthType.DXA },
            shading: { fill: i % 2 === 0 ? LIGHT : "FFFFFF", type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({ children: [new TextRun({ text: k, bold: true })] })],
          }),
          new TableCell({
            borders,
            width: { size: colB, type: WidthType.DXA },
            shading: { fill: i % 2 === 0 ? LIGHT : "FFFFFF", type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({ children: [new TextRun({ text: v })] })],
          }),
        ],
      })
    ),
  });
}

// Build a multi-column table with header row
function gridTable(headers, rows, columnWidths) {
  const widths = columnWidths || headers.map(() => Math.floor(CONTENT_WIDTH / headers.length));
  // adjust last so they sum exactly
  const sum = widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += CONTENT_WIDTH - sum;

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      new TableCell({
        borders,
        width: { size: widths[i], type: WidthType.DXA },
        shading: { fill: HEADER_FILL, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 120, right: 120 },
        children: [
          new Paragraph({
            children: [new TextRun({ text: h, bold: true, color: "FFFFFF" })],
          }),
        ],
      })
    ),
  });

  const dataRows = rows.map((row, ri) =>
    new TableRow({
      children: row.map((cell, ci) =>
        new TableCell({
          borders,
          width: { size: widths[ci], type: WidthType.DXA },
          shading: { fill: ri % 2 === 0 ? "FFFFFF" : LIGHT, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: cell })] })],
        })
      ),
    })
  );

  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...dataRows],
  });
}

// horizontal rule via paragraph border
const hr = () =>
  new Paragraph({
    children: [new TextRun({ text: "" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 1 } },
    spacing: { before: 120, after: 240 },
  });

const spacer = (after = 120) =>
  new Paragraph({ children: [new TextRun({ text: "" })], spacing: { after } });

// ---------- content sections ----------

const coverPage = [
  spacer(2400),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "PASSENGER INTELLIGENCE SERVICE", bold: true, size: 48, color: NAVY })],
    spacing: { after: 240 },
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Technical Whitepaper", size: 32, color: ACCENT })],
    spacing: { after: 480 },
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Edge AI for European Rail — Real-time passenger intelligence, delivered as a service", italics: true, size: 24 })],
    spacing: { after: 720 },
  }),
  hr(),
  spacer(240),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Nomad Digital", bold: true, size: 28 })],
    spacing: { after: 120 },
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Reference engagement: ÖBB (Austrian Federal Railways)", size: 22 })],
    spacing: { after: 480 },
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Version 1.0 — May 2026", size: 20, color: "666666" })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

const execSummary = [
  h1("1. Executive Summary"),
  p("The Passenger Intelligence Service is a managed, privacy-by-design edge-AI platform that gives rail operators real-time visibility into what is happening inside every coach of every train in their fleet. It runs on a single Hailo-8 neural accelerator deployed in the existing Nomad Digital onboard CCU, transforms onboard video and telemetry into structured operational insight in under a second, and never lets raw video leave the train."),
  p("The product addresses a problem every modern rail operator has but few have solved: train staff manage passenger flow, congestion, and safety incidents through direct observation — walking the train, visual checks, radio communication. A conductor walking a 10-coach train takes 3–5 minutes; overcrowding and door incidents resolve faster than that. Landside operations have no real-time view of individual train occupancy. The result is slow, incomplete, reactive operations that do not scale to fleet level."),
  p("Our solution delivers six core onboard capabilities — live per-coach occupancy, luggage detection with unattended-bag alerting, vestibule and rack congestion mapping, door obstruction detection, accessibility (wheelchair / pushchair / ramp) detection, and live TCMS alarm surfacing — alongside a cloud-hosted Control Centre Dashboard, an analytics and reporting layer, and role-specific interfaces for the conductor, driver, bistro, and capacity planning teams."),
  p("All inference runs onboard on the Hailo-8 accelerator. Only structured, anonymised events are transmitted to the cloud over the train’s existing Nomad SYS1 connectivity. The system continues to operate fully when the train is offline (tunnels, dead zones, broker outages) and reconciles transparently on reconnection."),
  p("This document describes the product, the architecture, the data and security model, and the deployment posture. It is intended for both the technical and commercial members of your evaluation team."),
  hr(),
];

const productOverview = [
  h1("2. What the Product Does"),

  h2("2.1 Capability Summary"),
  p("The service is organised around six onboard intelligence capabilities and three classes of landside interface. Each onboard capability is delivered by an inference pipeline running on the Hailo-8, fused with non-video telemetry from the train’s existing onboard VLANs."),

  gridTable(
    ["Capability", "What it does", "Primary consumers"],
    [
      ["Live occupancy", "Real-time per-coach passenger headcount derived from camera tripwire counting at door thresholds, calibrated against onboard APC hardware.", "Conductor App, Control Centre, PIS, Driver Display"],
      ["Luggage detection", "Per-coach luggage item count with unattended-bag alert raised when a bag remains stationary beyond a configurable timer.", "Conductor App, Control Centre"],
      ["Congestion mapping", "Coach-level green/amber/red colour-coded congestion diagram, including vestibule and luggage-rack saturation states.", "Conductor App, Passenger Portal, Control Centre"],
      ["Door obstruction detection", "Camera + door-fault sensor correlation that detects passengers or items blocking doors, with severity escalation when the train is in motion.", "Conductor App, Driver, Control Centre"],
      ["Accessibility detection", "Wheelchair and pushchair detection with door correlation and ramp-deployment alerting, surfaced to conductor, platform staff, and the passenger.", "Conductor App, Passenger Portal"],
      ["TCMS alarm ingestion", "SNMP polling of Stadler / TCMS alarms with plain-language translation, surfaced by severity and speed-correlated escalation.", "Conductor App, Driver, Control Centre"],
    ],
    [1600, 5500, 2260]
  ),

  spacer(120),
  h2("2.2 Interface Surfaces"),
  p("The service exposes intelligence through a set of role-specific interfaces. Each is designed around the actual decision the user needs to make — not around the underlying data model."),

  gridTable(
    ["Interface", "User", "Form factor"],
    [
      ["Control Centre Dashboard", "Control Centre Operator", "Cloud-hosted web SPA, 1440px+ desktop"],
      ["Conductor App", "Conductor / Train Manager", "Mobile PWA on staff VLAN handheld"],
      ["Driver Display", "Driver", "Cab-mounted read-only screen"],
      ["Passenger Information System", "Passengers", "Onboard PIS exterior + interior displays"],
      ["Bistro App", "Catering staff", "Mobile, lightweight load view"],
      ["Maintenance Dashboard", "Fleet Maintenance Manager", "Web, historical & system-health view"],
      ["Capacity Planner Reports", "Capacity Planner", "Web reports, aggregated analytics"],
    ],
    [3000, 3000, 3360]
  ),

  spacer(120),
  p("In the current pilot scope (Phase 1), the Control Centre Dashboard is the primary landside interface and the Conductor App is the primary onboard interface. The remaining interfaces are sequenced in Phase 2."),

  h2("2.3 Service Tiers"),
  p("Capabilities are grouped into three commercial tiers that map cleanly to the operator value chain:"),
  bullet("Tier 1 — Core Intelligence: occupancy, congestion, door safety. The operational baseline."),
  bullet("Tier 2 — Operational Excellence: luggage, accessibility, TCMS alarm surfacing, predictive overcrowding."),
  bullet("Tier 3 — Experience & Insight: passenger-facing portal, analytics, ESG reporting, ridership intelligence."),
  p("Operators can adopt at any tier and progress as their organisation matures around the data."),
  hr(),
];

const architecture = [
  h1("3. Architecture"),

  h2("3.1 Architectural Principles"),
  bullet("Edge-first: all video inference runs onboard. Raw video never leaves the train. Only structured, anonymised events traverse the cloud boundary."),
  bullet("Offline-tolerant: every onboard interface remains fully functional during connectivity outages. The Control Centre Dashboard is the only surface that is cloud-dependent by design, and degrades gracefully."),
  bullet("Idempotent and replayable: every event carries a stable identity (journey_id + event_id) so the cloud layer can absorb retries, out-of-order delivery, and post-tunnel resync without duplication or loss."),
  bullet("Containerised and replicable: each train runs an identical Docker-compose stack. Horizontal scale-out is by-vehicle, not by-cluster."),
  bullet("Schema-first: a single canonical event envelope and a versioned EventType taxonomy are shared by every producer and consumer in the system."),

  h2("3.2 Onboard Edge Stack"),
  p("Onboard, the platform runs as five cooperating containers on SYS2 of the Nomad Digital R5001C CCU (Debian 12 + Docker, with a Hailo-8 M.2 accelerator on PCIe Gen 3 x4):"),

  gridTable(
    ["Container", "Responsibility"],
    [
      ["rtsp-ingest", "Connects to onboard CCTV cameras (VLAN 5) and pulls H.264 streams. Manages per-camera priority and frame-buffer allocation. Hands raw frames to the inference pipeline."],
      ["inference", "Hosts the Hailo-8 inference pipeline. Runs yolov8m for detection and yolov8m_pose for accessibility/fall-detection zones. Uses the native hailotracker (Kalman + IoU) for stable track IDs across frames."],
      ["vlan-pollers", "Polls the non-video onboard VLANs: APC (door counts), ZFR (train control), TCMS (Stadler SNMP), PIS, reservations, bistro, and energy meters. Normalises everything to the event envelope."],
      ["fusion", "The local fusion engine. Correlates camera-derived counts with APC ground truth, runs the closed-ledger reconciliation between coaches, applies the suppression state machine, and emits operator-grade alerts."],
      ["event-store", "Local SQLite event store (WAL mode, single-writer). Exposes the onboard REST + WebSocket API and manages the sync cursor that pushes structured events to the cloud."],
    ],
    [2200, 7160]
  ),

  spacer(120),
  p("The five containers communicate over a private Docker network. event-store is the only HTTP surface on the CCU. All inter-container clients use httpx with exponential backoff and a startup health-check loop so the stack is tolerant of container start-order."),

  h2("3.3 Camera-Primary Passenger Counting"),
  p("Passenger counting is camera-primary. Directional tripwire polygons are configured at every door threshold. As the Hailo-8 tracker assigns stable IDs to detected persons, the fusion engine atomically increments or decrements the coach count when a track crosses the entry or exit side of a tripwire. Boarding and alighting are observed as directional flows, not just net deltas."),
  p("APC (Automatic Passenger Counting) hardware data is retained as a calibration reference. The system compares the camera-derived count to the APC count on every poll cycle; if the delta exceeds a configurable threshold (default ±10 passengers per coach), a calibration drift event is emitted. APC does not modify the live occupancy count."),
  p("Per-coach seated-vs-standing distribution is calculated by intersecting detection bounding boxes with pre-configured static zone polygon masks (seating, aisle, vestibule, door-threshold). Pose estimation is reserved for accessibility spaces and vestibule fall-detection zones, where it earns its compute budget."),

  h2("3.4 Inter-Wagon Movement Ledger"),
  p("Passenger movement between coaches is tracked via virtual directional tripwires at each gangway camera using a closed-ledger accounting model. When a tracked person crosses the exit polygon of coach N, a WAGON_EXIT event is emitted; when the same track ID crosses the entry polygon of coach N+1 within a short window, the pair is reconciled and ledger counts are updated."),
  p("The local fusion engine maintains a coach_ledger SQLite table tracking, per coach: ledger_count, unreconciled exits, and last reconciled timestamp. Any drift between camera-derived occupancy and ledger-derived occupancy is detected by drift-bucket transitions and emitted as a diagnostic observation. The ledger self-corrects to the camera count on each transition. Drift observations are diagnostic telemetry by default and are promoted to operator alerts only on station approach."),

  h2("3.5 Operational Telemetry Fusion"),
  p("The fusion engine applies three cross-correlation rules that transform raw camera + VLAN data into operator-grade signal:"),
  numbered("Door-release → platform camera priority: when the train control system reports doors released for a coach, fusion issues an internal stream-priority command to rtsp-ingest, nominating the platform-facing cameras of that coach for higher frame budget during the dwell window."),
  numbered("Coach comfort index: a per-coach comfort score, emitted on configurable occupancy delta and again on station-approach edge transitions. Phased upgrade path to incorporate environmental sensor data (temperature, noise) and reservation-system data when those VLAN feeds are confirmed available."),
  numbered("GPS / HAFAS proximity alert escalation: when the train is within two minutes of a scheduled stop, any alert raised in that window receives an escalated priority flag, surfacing it with elevated urgency in the Control Centre Dashboard."),

  h2("3.6 Cloud Backend"),
  p("The cloud layer is a FastAPI + PostgreSQL service that ingests events from the onboard fleet, serves the Control Centre Dashboard, and hosts the analytics layer. Key design points:"),
  bullet("Two-table model: a journeys table holds journey metadata; an events table holds all events with a JSONB payload, linked by journey_id."),
  bullet("DB-enforced idempotency: a UNIQUE constraint on (journey_id, event_type, source_timestamp) is the authoritative dedup mechanism. Application-level dedup is defence-in-depth only."),
  bullet("Real-time push: the Control Centre Dashboard receives live updates over WebSocket / SSE with client-driven subscriptions (event types, minimum severity, coach IDs) and a configurable reconnect replay depth that prevents silent gaps after disconnection."),
  bullet("Versioned, prefix-stable REST API: every endpoint is published under /api/v1/ from day one."),
  bullet("Hosting-agnostic event envelope: the canonical event schema is locked independently of the hosting decision, so cloud deployment can move between Nomad-owned and hyperscaler infrastructure without schema churn."),

  h2("3.7 Event Envelope"),
  p("Every event written anywhere in the system uses the same canonical envelope:"),
  new Paragraph({
    spacing: { before: 60, after: 120 },
    shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
    children: [
      new TextRun({ text: "{", font: "Consolas" }),
      new TextRun({ text: "  \"event_id\": \"<uuid-v4>\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"journey_id\": \"<vehicle_id>_<trip_number>_<YYYYMMDD>\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"vehicle_id\": \"<string>\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"timestamp\": \"<ISO-8601 UTC>\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"event_type\": \"<EventType enum>\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"severity\": \"critical | warning | info\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"source\": \"inference | fusion | vlan-pollers\",", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"schema_version\": 1,", font: "Consolas", break: 1 }),
      new TextRun({ text: "  \"payload\": { ... }", font: "Consolas", break: 1 }),
      new TextRun({ text: "}", font: "Consolas", break: 1 }),
    ],
  }),
  p("The journey_id scheme uses the journey start date (not event date), so journeys spanning midnight do not break their key. Schema version is mandatory; consumers must reject unsupported versions with a structured warning rather than crash."),

  hr(),
];

const dataFlows = [
  h1("4. Data Flows"),

  h2("4.1 The Live Alert Path"),
  p("From video frame to a conductor’s screen, the live alert path looks like this:"),
  numbered("rtsp-ingest pulls a frame from the relevant CCTV camera at the priority-appropriate frame rate (10 fps for P1 door / vestibule cameras, 5 fps for interior, 8 fps for exterior cameras only during the station window)."),
  numbered("inference runs Hailo-8 detection and tracking on the frame. The hailotracker assigns or updates a stable track ID. Track + bounding-box metadata flows through GStreamer buffer metadata into a Python callback layer."),
  numbered("If the track crosses a tripwire polygon, the inference container POSTs an occupancy update to event-store and forwards a candidate event to fusion via the canonical /candidates endpoint."),
  numbered("fusion correlates the candidate against APC drift, the closed-ledger state, the suppression state machine, and any cross-VLAN signals (door release, GPS proximity, maintenance mode). If the event survives, it is emitted as an operator-grade event."),
  numbered("event-store persists the event to SQLite (WAL mode, single-writer) and fans it out to onboard subscribers over WebSocket. The Conductor App receives the update with sub-second latency."),
  numbered("The same event is appended to the cloud sync buffer. When SYS1 connectivity is available, the sync cursor flushes the buffer to the cloud backend. The cloud backend ingests it idempotently and fans it out to the Control Centre Dashboard."),

  h2("4.2 The Resilience Path"),
  p("Trains spend a non-trivial amount of time in tunnels, dead zones, and depot environments where cloud connectivity is degraded. The system absorbs these conditions without operator-visible impact:"),
  bullet("Onboard interfaces (Conductor App, Driver Display, PIS, Passenger Portal) read directly from the local event-store. They are unaffected by cloud connectivity."),
  bullet("The sync cursor maintains a last_synced_event_id, updated atomically only when the cloud acknowledges a batch. On restart or reconnection, the cursor re-syncs from the last acknowledged position; the DB unique constraint deduplicates transparently."),
  bullet("SQLite retains a configurable journey ring buffer (default: last 3 journeys) as a debug and replay window."),
  bullet("WebSocket clients (including the Control Centre Dashboard) declare a reconnect replay depth at connection time; the server replays the last N matching events after reconnection so safety-relevant alerts (door obstruction, unattended bag, alert raised) are never silently missed."),

  h2("4.3 Suppression State Machine"),
  p("False positives are the single largest threat to operational adoption of AI systems in rail. The platform manages this with a formal, explicit suppression state machine. Alerts are suppressed when any of the following hold:"),
  bullet("The train is in depot maintenance mode."),
  bullet("Train control reports a degraded operation or shutdown-all state."),
  bullet("GPS is invalid or below quality threshold."),
  bullet("Coupling-in-progress (multi-CCU topology, post-PoC)."),
  p("Transitions between suppression states are explicit, logged, and — for safety-relevant transitions — require operator sign-off before implementation. The suppression layer applies uniformly across all alert classes; nothing bypasses it."),

  hr(),
];

const privacySecurity = [
  h1("5. Privacy, Security, and Compliance"),

  h2("5.1 Privacy by Design"),
  p("The platform was designed against a single non-negotiable rule: raw video must never leave the train. Every architectural decision follows from that constraint."),
  bullet("All inference is local. Camera frames are processed on the Hailo-8 onboard and discarded; only structured detection results enter the event pipeline."),
  bullet("Cloud sync transmits structured events only. Event payloads are aggregated counts, anomaly flags, and metadata — never images, video segments, or biometric vectors."),
  bullet("Personal identity is not constructed. Track IDs are local, ephemeral, and reset on container restart. The platform does not perform face recognition or any form of re-identification."),
  bullet("Every event is journey-scoped. Deletion requests (operator or regulatory) can be honoured at journey granularity rather than searching across an unstructured log."),

  h2("5.2 GDPR Posture"),
  p("Event payloads are anonymised aggregate by construction. Every event carries journey_id, vehicle_id, and an ISO-8601 UTC timestamp — sufficient metadata to support legitimate operational and analytics use, scoped tightly enough to support deletion and data-minimisation obligations. The data retention policy is configurable per deployment and is applied uniformly at the cloud boundary."),

  h2("5.3 Authentication and Network Boundaries"),
  p("Onboard, staff interfaces (Conductor App, Driver Display) sit on the staff VLAN (VLAN 30) and are trusted by network membership in PoC scope. The Passenger Portal sits on VLAN 10 (passenger WiFi) with no auth — it is read-only by design. The upgrade path to token-based authentication (JWT) is a named Phase 2 deliverable, gated explicitly by multi-conductor deployment, contractual security requirements, or passenger-service-grade operation."),
  p("At the cloud boundary, the Control Centre Dashboard authenticates to the backend via API key in PoC scope, with a clean upgrade path to OAuth2 / OIDC integration with the operator’s identity provider at fleet rollout. No API key or credential ever appears in source control — PoC uses .env management, fleet uses Docker secrets, and pre-commit hooks block credential strings from being committed."),

  h2("5.4 Prompt Injection Boundaries"),
  p("All data arriving from external sources — Hailo inference results, VLAN poller outputs (SNMP, APC, PIS/FIS), MQTT payloads — is treated as untrusted. A sanitisation and skepticism layer validates schema, rejects unexpected fields, and logs anomalies before any of it influences an AI-driven decision (occupancy alert, comfort score, anomaly detection). Raw external payloads are never passed unconstrained into downstream model context."),

  h2("5.5 Credential Hygiene"),
  p("VLAN poller and Hailo ingest credentials never pass through inference code paths. Authentication flows via resource initialisation (credentials bundled at container startup via environment variables) or via an external vault / proxy. This boundary is audited on every change that touches the ingest, polling, or inference layers."),

  hr(),
];

const opsModel = [
  h1("6. Deployment and Operations"),

  h2("6.1 Onboard Footprint"),

  kvTable([
    ["Edge hardware", "Single Hailo-8 M.2 (26 TOPS, PCIe Gen 3 x4) on ADLINK cPCI-A3H20 blade, mounted in SYS2 of the Nomad R5001C CCU"],
    ["Host OS", "Debian 12 + Docker"],
    ["Runtime", "HailoRT + TAPPAS (GStreamer-based)"],
    ["Operating temperature", "-40°C to +85°C (rail-compliant)"],
    ["Container count", "5 (rtsp-ingest, vlan-pollers, inference, fusion, event-store)"],
    ["Local store", "SQLite (WAL mode), journey-scoped, with sync cursor"],
    ["Camera capacity", "25–30 cameras per train (validated TOPS budget)"],
    ["Onboard API", "REST + WebSocket served by event-store"],
  ]),

  spacer(120),
  h2("6.2 Cloud Footprint"),

  kvTable([
    ["API", "FastAPI + Uvicorn"],
    ["Database", "PostgreSQL (events + journeys tables, JSONB payloads)"],
    ["Real-time push", "WebSocket + Server-Sent Events with client-driven subscriptions and reconnect replay"],
    ["Hosting", "Cloud-agnostic — deployable to Nomad-owned infrastructure or hyperscaler (Azure / AWS)"],
    ["Auth (PoC)", "API key per deployment"],
    ["Auth (fleet)", "OAuth2 / OIDC with operator IdP"],
  ]),

  spacer(120),
  h2("6.3 Delivery Model"),
  p("The Passenger Intelligence Service is delivered as a fully managed AI Insights-as-a-Service offering on a per-train monthly subscription. Nomad Digital operates the cloud backend, manages onboard container deployments via the existing SYS1 remote management channel, monitors fleet-wide health, ships model updates, and owns the SLA. The operator receives a deployed, monitored service — not a tarball."),

  h2("6.4 CI/CD and Quality Gates"),
  p("The build and release pipeline runs on GitLab CI/CD with the following stages enforced on every commit:"),
  bullet("ruff (linting, with Python 3.11 upgrade rules enabled)"),
  bullet("mypy --strict (static typing)"),
  bullet("bandit (Python security scanning)"),
  bullet("detect-secrets (credential leak prevention)"),
  bullet("pytest with coverage (≥80% enforced via pytest-cov --cov-fail-under=80)"),
  p("Test coverage spans three layers: unit tests for pure logic with no I/O, integration tests using testcontainers-python (real PostgreSQL, real SQLite, never mocked at the DB layer), and contract tests that verify schema-version compatibility between producers and consumers."),

  h2("6.5 Observability"),
  p("All onboard containers emit structured JSON logs to local files with logrotate. Every log line carries at minimum: timestamp, container name, level, event type, journey_id (when bound), and a descriptive action keyword. Correlation IDs propagate automatically via structlog context binding, so a single journey can be traced end-to-end without manual stitching."),
  p("No log aggregation service is in scope for PoC; structured logs are retrievable via the existing SYS1 remote management channel. Aggregation tooling is straightforward to add at fleet rollout because the log format is already structured and consistent."),

  hr(),
];

const nonFunctional = [
  h1("7. Non-Functional Targets"),
  p("The following targets are committed for the PoC and form the baseline SLA negotiated at fleet rollout:"),

  gridTable(
    ["Target", "Value", "How it is achieved"],
    [
      ["System uptime", "≥99.5%", "Docker restart policies; graceful degradation on SYS1 loss; per-train independence (no cross-train dependencies)"],
      ["Occupancy accuracy", "≥95%", "Camera-primary counting with APC calibration drift detection; static zone masks per coach type"],
      ["False-positive alert rate", "<5%", "Formal suppression state machine; multi-signal fusion (camera + sensor + train state)"],
      ["Alert latency", "Within dwell window (~30–90s)", "Local inference; local API; no cloud round-trip required for any onboard alert"],
      ["Privacy", "Raw video never leaves train", "Edge-only inference; anonymised structured events only over cloud sync"],
      ["Connectivity resilience", "Onboard interfaces fully functional when SYS1 is down", "Local SQLite event store; offline-first onboard UIs; sync cursor with idempotent cloud ingest"],
      ["Test coverage", "≥80%", "pytest-cov --cov-fail-under=80 enforced in CI"],
    ],
    [1900, 1800, CONTENT_WIDTH - 3700]
  ),
  spacer(120),
  hr(),
];

const integration = [
  h1("8. Integration Surfaces"),

  h2("8.1 Onboard Data Sources"),
  p("The platform integrates with the following onboard VLANs already present on Nomad-equipped trains. No additional onboard cabling or network changes are required to deploy the service on a Nomad-instrumented fleet."),

  gridTable(
    ["VLAN", "Source", "Used for"],
    [
      ["VLAN 5", "CCTV cameras (H.264 RTSP)", "All vision-based capabilities"],
      ["VLAN 8", "Automatic Passenger Counting (door sensors)", "Calibration reference for camera-derived occupancy"],
      ["VLAN 7", "Stadler train control / TCMS (SNMP)", "Alarm ingestion, door state, GPS / HAFAS"],
      ["VLAN 3", "PIS / FIS displays", "Display push (read or write, depending on operator)"],
      ["VLAN 6", "Reservation system", "Phase 2 — reservation-vs-actual occupancy correlation"],
      ["VLAN 2", "ZFR train control", "Door release, train motion state"],
      ["VLAN 12", "Energy meters", "Occupancy-normalised ESG KPIs"],
      ["VLAN 46–48", "Bistro telemetry", "Phase 2 — catering optimisation"],
    ],
    [1200, 3800, CONTENT_WIDTH - 5000]
  ),

  spacer(120),
  h2("8.2 Landside Interfaces"),
  p("On the landside, the cloud backend exposes:"),
  bullet("A REST API under /api/v1/ for synchronous query (events, journeys, analytics aggregates)."),
  bullet("A WebSocket / SSE endpoint for real-time event delivery, with client-driven subscriptions and reconnect replay."),
  bullet("Standard error envelopes (error code, human-readable detail, recoverable flag) on every error path."),
  bullet("Cursor-based pagination on all list endpoints (offset pagination is rejected because it breaks under concurrent event writes)."),
  p("The intended integration target for partner operators is operator-side identity (via OAuth2 / OIDC at fleet rollout), operator-side incident management (deep-link from any escalation to the operator’s ticketing system), and operator-side analytics warehouses (event export under data-sharing agreement)."),

  h2("8.3 What We Do Not Replace"),
  p("The platform deliberately does not replace existing operator systems. It supplements them:"),
  bullet("It does not replace train control or safety systems. It observes them and surfaces their state in plain language."),
  bullet("It does not replace the operator’s CCTV review tooling. It runs alongside, processing the same cameras at the edge."),
  bullet("It does not replace incident management. It feeds into it."),
  bullet("It does not replace the operator’s data warehouse. It feeds structured event exports into it."),

  hr(),
];

const roadmap = [
  h1("9. Roadmap and Phasing"),

  h2("9.1 Phase 1 — Operational PoC"),
  p("Current phase. Single-vehicle pilot validating the full edge → cloud → dashboard path with the six core onboard capabilities, the Control Centre Dashboard, and the analytics layer. Three-month timeline."),

  h2("9.2 Phase 1.1 — Passenger Portal"),
  p("Public-facing onboard portal surfacing per-coach load guidance, accessibility status, and ramp-confirmed states to passengers boarding and travelling. Deferred from Phase 1 pending design delivery."),

  h2("9.3 Phase 2 — Onboard Interface Expansion"),
  p("Roll-out of the remaining role-specific interfaces:"),
  bullet("Conductor App as a production PWA with validated offline mode"),
  bullet("Bistro App for catering load and trolley routing"),
  bullet("Driver Display productionisation"),
  bullet("PIS exterior + interior screens once L2 write access is confirmed with the rolling-stock supplier"),
  bullet("Maintenance Dashboard for fleet engineering teams"),

  h2("9.4 Phase 2+ — Predictive and Diagnostic AI"),
  p("Beyond the operational baseline, the data layer enables:"),
  bullet("AI-generated fault pattern detection across the fleet"),
  bullet("Predictive fault alerting from telemetry trend analysis"),
  bullet("Natural-language diagnostics agent (integrated with Nomad’s Nomie backend)"),
  bullet("Automated cleaning work orders from observed coach state"),
  bullet("Energy anomaly flagging from occupancy-normalised KPIs"),
  bullet("Bistro demand intelligence and boarding-volume prediction"),

  h2("9.5 Fleet Rollout"),
  p("Architectural decisions made during Phase 1 have been chosen to keep fleet rollout as a configuration exercise, not an architecture exercise: per-vehicle docker-compose, no cross-vehicle onboard state, idempotent cloud ingest, hosting-agnostic event envelope, planned PostgreSQL HA gate, planned OAuth2 / OIDC gate."),

  hr(),
];

const closing = [
  h1("10. Why This Architecture"),
  p("Three structural choices distinguish this platform from a generic edge-AI offering:"),
  p("First, the data position. The platform is built on top of the operator’s existing Nomad Digital CCU, with read access to every onboard VLAN. The intelligence is therefore multi-source from day one: camera + APC + TCMS + train control + reservations + energy. A vision-only competitor would need to replace network infrastructure to match this."),
  p("Second, the privacy boundary. By keeping raw video onboard and transmitting only structured events, the platform avoids the regulatory and procurement friction that a cloud-video architecture creates. Every event is journey-scoped and deletable at journey granularity."),
  p("Third, the delivery model. The service is sold per-train per-month, fully managed. The operator gets continuous improvement (model updates, new capabilities, refined fusion rules) as part of the subscription, without taking on the operational burden of running an ML platform."),
  p("These three properties compose. The data position makes the intelligence valuable; the privacy boundary makes the intelligence deployable; the delivery model makes the intelligence sustainable."),
  hr(),
  spacer(120),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: "For technical follow-up:", italics: true }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: "Nomad Digital — Passenger Intelligence Service", bold: true }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: "abbas.rizvi@nomadrail.com", color: ACCENT }),
    ],
  }),
];

// ---------- assemble document ----------

const doc = new Document({
  creator: "Nomad Digital",
  title: "Passenger Intelligence Service — Technical Whitepaper",
  description: "Technical description of the Passenger Intelligence Service for prospective rail operator customers.",
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 22 } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Calibri", color: NAVY },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: NAVY },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: "Calibri", color: ACCENT },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 },
      },
    ],
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
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
          {
            level: 1,
            format: LevelFormat.BULLET,
            text: "◦",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1440, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "numbers",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH, height: 15840 },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: ACCENT, space: 4 } },
              children: [
                new TextRun({ text: "Passenger Intelligence Service — Technical Whitepaper", size: 18, color: "666666" }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              children: [
                new TextRun({ text: "Nomad Digital — Confidential", size: 18, color: "666666" }),
                new TextRun({ text: "\t", size: 18 }),
                new TextRun({ text: "Page ", size: 18, color: "666666" }),
                new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "666666" }),
                new TextRun({ text: " of ", size: 18, color: "666666" }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: "666666" }),
              ],
            }),
          ],
        }),
      },
      children: [
        ...coverPage,
        ...execSummary,
        ...productOverview,
        ...architecture,
        ...dataFlows,
        ...privacySecurity,
        ...opsModel,
        ...nonFunctional,
        ...integration,
        ...roadmap,
        ...closing,
      ],
    },
  ],
});

const outPath = path.resolve(__dirname, "..", "..", "Passenger-Intelligence-Service-Whitepaper.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outPath, buffer);
  console.log("Wrote:", outPath, "(" + buffer.length + " bytes)");
});
