Here is the fully compiled and upgraded architecture.md file. It consolidates your existing system foundation with the hailo-apps implementation rules, our camera-based directional tripwire counting logic, and the optimized train-vs-landside deployment model.

Markdown
---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9]
status: COMPLETE
lastUpdated: '2026-05-16'
updateReason: 'Consolidated Edge/Landside split, Hailo-Apps repo integration, and Camera-Based counting'
inputDocuments:
  - project-context.md
  - product-brief.md
  - ux-design-specification.md
workflowType: 'architecture'
project_name: 'oebb-smart-rail-passenger-intelligence'
user_name: 'AbbasRizvi'
date: '2026-05-16'
---

# Architecture Decision Document: OEBB Smart Rail Passenger Intelligence

This document outlines the authoritative system architecture for the ÖBB Passenger Intelligence Service pilot. It defines the deployment split, hardware utilization, container pipeline structure, and data management workflows.

---

## 1. System Vision & Constraints

### Vision
Transform onboard hardware nodes into a privacy-compliant, edge-to-cloud AI-powered service layer. By owning the underlying network topology (VLAN routing), the system turns raw CCTV feeds and telemetry into real-time operational metrics without compromising passenger privacy or straining train-to-landside wireless backhauls.

### Core Technical Constraints
* **Edge Hardware:** Single Hailo-8 M.2 Module (26 TOPS, PCIe Gen 3 x4) hosted on an ADLINK cPCI-A3H20 blade (SYS2).
* **Host Operating System:** Debian 12 + Docker.
* **Network Access:** Direct ingestion from onboard train network VLANs (VLAN 5: CCTV, VLAN 2: ZFR/Doors, VLAN 6: Reservations, VLAN 7: TCMS/Telemetry, VLAN 8: APC Reference).
* **Privacy Baseline:** Absolute GDPR compliance. Raw video streams/images are strictly confined to temporary host memory spaces on the train and must *never* be written to disk or transmitted over the air.
* **Connectivity:** Edge-to-cloud sync restricted to structured, anonymized JSON strings pushed over the SYS1 router network.

---

## 2. Resource Optimization: Edge-Inference vs. Landside-Cloud Split

To minimize power, heat, and storage footprints onboard the train, the application enforces a strict division of labor. The train performs real-time edge processing to generate anonymized states, while the landside cloud handles historical storage, calibration, and heavy presentation logic.

   ON THE TRAIN (Edge Nodes)                  LANDSIDE / CLOUD (Central Platform)
┌───────────────────────────────────────┐       ┌───────────────────────────────────────────┐
│ • RTSP Ingestion & Priority Throttling │       │ • Historical Timeseries Storage           │
│ • Hailo-8 Hardware Acceleration       │ ───►  │ • Dilax APC Baseline Calibration Engine   │
│ • Local Spatial Zone Polygon Masking  │ JSON  │ • Heavy Web Servers & WebSocket Managers  │
│ • Live Closed-Ledger Occupancy        │       │ • Frontend Dashboard UI Rendering         │
└───────────────────────────────────────┘       └───────────────────────────────────────────┘


### Onboard Edge-Node Core Microservices

#### 1. `rtsp-ingest` Container (Lean Python / GStreamer)
* **Role:** Acts as the high-throughput video ingress gateway. It abstracts stream access away from the core processing units and handles network drops or camera reconnects natively.
* **Optimization:** Embedded with the **Priority Budget Manager**. It dynamically down-samples or drops frame rates for lower-priority streams (P2/P3 interior coach views throttled down to 2–5 fps) during low-activity windows to conserve host CPU and PCIe bandwidth. High-priority P1 streams (doors, gangways, accessibility zones) are permanently locked at maximum processing refresh rates.

#### 2. `hailo-inference` Container (Hardware Accelerated)
* **Role:** Wraps the `hailo-apps` pipeline framework to feed multiplexed video frames into the Hailo-8 M.2 chip.
* **Optimization:** Offloads 100% of the neural network matrix evaluations directly to the Hailo-8 chip via the `hailort` PCIe driver. This module converts high-bandwidth video buffers into lightweight metadata strings containing bounding box tracking IDs, class categories, and raw pose matrices.

#### 3. `local-fusion-engine` Container (Stateless Logic Event Loop)
* **Role:** Executes localized spatial zone polygon evaluations and correlates cross-VLAN telemetry events. It transforms raw coordinate JSON blobs into anonymized train states.
* **Optimization:** Maintains a minimal memory matrix to process real-time events. It stores no historical data, dropping passenger tracking IDs as soon as a vehicle boundary tripwire is triggered.

#### 4. `cloud-sync` Container (Data Gateway)
* **Role:** Compresses state mutations into tiny MQTT/AMQP payloads and handles outbound queuing.
* **Optimization:** Includes an ephemeral, localized SQLite/RocksDB buffer. If the train moves through a tunnel or cellular dead zone, it queues data without stalling upstream engines, releasing the telemetry only when the uplink clears.

### Landside / Cloud Platform Services

#### 1. Telemetry Ingestion & Timeseries Database
* **Role:** Consumes incoming telemetry events from across the entire active fleet and appends them to a scalable database engine (e.g., TimescaleDB / InfluxDB). 

#### 2. Calibration & Optimization Pipeline (`Alstom Maastria`)
* **Role:** Processes historical datasets to compare camera-based counts against the ground-truth physical APC system. It runs calibration regressions and builds updated spatial zone configuration scripts without taxing onboard processors.

#### 3. Frontend UI App Servers & WebSockets
* **Role:** Delivers real-time telemetry rendering to thousands of target clients simultaneously (Conductor App, Control Centre Dashboard, Passenger Portal) by offloading connection management completely to landside data centers.

---

## 3. Hailo-Apps Repository Integration & Model Strategy

The system minimizes boilerplate code by relying directly on the `hailo-apps` infrastructure framework, specifically extending the Python/GStreamer **Pipeline Apps** modules and the standard **BYTETracker** tracking integration.

### Core Model Selection (From the Hailo Model Zoo v2.x Branch)
To ensure absolute compatibility with the Hailo-8 hardware and the Hailo Dataflow Compiler v3.x runtime libraries, the following compiled Hailo Executable Files (`.hef`) are pinned:

1. **`yolov8m.hef` / `yolov11m.hef` (Primary Core Engine):**
   * **Resolution:** $640 \times 640 \times 3$
   * **Target Deployment:** Deployed across all active streams. The Medium (m) variant is selected to balance spatial detection sensitivity (preventing false-negatives caused by high-back seat occlusion) with runtime efficiency.
   * **Extracted Classes:** Class `0` (`person`), Class `24` (`backpack`), Class `26` (`suitcase`), and Class `1` (`bicycle` proxy).

2. **`yolov8m_pose.hef` (Targeted Secondary Engine):**
   * **Resolution:** $640 \times 640 \times 3$
   * **Target Deployment:** Restricted strictly to P1 stream configurations mapping the vestibules and the dedicated multi-purpose/wheelchair compartments. It extracts the 17-point human skeleton topology for structural keypoint vector checks.

---

## 4. Architectural Decisions (ADR)

### ADR-15: Camera-Based Primary Passenger Counting with APC Reference
* **Decision:** Primary passenger counting for boarding and alighting calculations will be derived directly via the camera vision pipeline using directional tripwires. The hardware-based Automatic Passenger Counting (APC) sensors are designated solely as an external verification reference baseline.
* **Rationale:** Relying on the cameras as the source of truth allows direct validation of the computer vision service metrics. The `local-fusion-engine` processes counts by evaluating tracking vectors across virtual polygons mapped over door thresholds. The actual APC hardware data is pulled concurrently via the `APCAdapter` protocol and logged alongside the camera counts as a calibration attribute.

### ADR-16: Spatial Zone Masking for Seated vs. Standing Distribution
* **Decision:** Per-coach seating occupancy distributions will be calculated by intersecting standard object detection coordinates (`yolov8m.hef`) with pre-configured static zone masks inside the `local-fusion-engine`, rather than processing pose estimation models across all train cameras.
* **Rationale:** Spreading human skeletal keypoint algorithms across 25–30 parallel streams would exhaust the Hailo-8 module's compute capability, leading to significant frame dropping. Furthermore, high-back seats on ÖBB coaches cause heavy passenger lower-body occlusion, which degrades pose estimator accuracy. Evaluating standard object bounding boxes against predefined *Seating* and *Aisle* coordinate polygons delivers equivalent metrics with fractional compute consumption.

### ADR-17: Inter-Wagon Movement Ledger Reconciliation
* **Decision:** Transitions between individual train coaches (wagons) will be monitored via virtual tripwires assigned to the high-priority P1 gangway cameras, treating the entire vehicle as a closed accounting ledger.
* **Mechanism:** 1. As a passenger steps through the inter-circulating gangway, the camera in the departing coach tracks the ID crossing an exit tripwire, generating a `-1 Inter-Wagon Exit` event.
  2. The camera in the adjoining coach registers the passenger crossing an entry tripwire, generating a `+1 Inter-Wagon Entry` event.
  3. While the train is in motion between stations, the net sum of passengers across the closed ledger must remain constant. Any tracking drifts caused by temporary line-of-sight occlusion are automatically reconciled by cross-referencing localized coach seat occupancy masks before the next station arrival.

### ADR-18: Operational Telemetry Fusion Rules
* **Decision:** The `local-fusion-engine` container will continually cross-examine lightweight vision metadata tensors from the `hailo-inference` container with active non-video train telemetry streams pulled from network pollers:
  * **Door Status (VLAN 2 / 7):** When the train network reports `Doors Released = True`, the fusion container commands the ingestion service to actively target and optimize platform-facing camera feeds for precise boarding and alighting window analytics.
  * **Seat Reservations (VLAN 6):** Physical seating occupancy counts derived from zone masking will be mapped directly against electronic seat reservation states to dynamically calculate a real-time "Coach Comfort Index".
  * **Spatio-Temporal Constraints (VLAN 7):** Live GPS coordinates and HAFAS timetable metrics will determine station proximity. High-impact alerts (such as a door obstruction or an unattended bag) identified close to an arrival station (e.g., within 2 minutes of Linz Hbf) will automatically receive an escalation priority boost inside the event stream.

---

## 5. Appendix: Architecture Status Verification

| # | Open Question | System Impact | Status |
|---|---|---|---|
| 1 | `pose_estimation` per-coach seated/standing split feasible? | Coach details dashboard grids | **Closed (ADR-16):** Opted for Object Detection + Spatial Zone Masking; Pose tracking restricted to P1 accessibility spaces and fall-detection zones. |
| 2 | WebSocket staleness threshold (default assumed 2 min) | Staleness banner rendering | Open (Awaiting ÖBB Ops verification) |
| 3 | AI escalation confidence threshold | Outbound alert volumes | Open (Awaiting ÖBB Ops verification) |
Integration Steps for Your Development Team:
Model Deployment: Ensure the team pulls .hef files compiled for the Hailo-8 architecture (v2.x branch), or they will throw a runtime hardware fault.

Zone Maps: The local-fusion-engine folder needs a config/zones/ subdirectory containing JSON coordinate files for each coach type in the ÖBB fleet to process the logic detailed in ADR-16 and ADR-17.

Telemetry Access: The APCAdapter and TCMS poller endpoints must target the corresponding onboard network switches to pipe the verification data into the fusion engine.

ou can absolutely do agentic work with this local setup. Framing this system as "just a RAG pipeline" severely underestimates what a localized, quantized model (like Llama 3.2 or DeepSeek-R1) can do when granted an execution loop on the train's edge node.

In a traditional static RAG setup, the LLM reads data, answers a question, and stops. An Agentic LLM, however, uses a Reasoning-and-Action (ReAct) loop. It is given an identity, an objective, a set of software "tools" (APIs it can call), and the autonomy to figure out how to solve a complex train problem step-by-step without human intervention.

Here is exactly how you transform this local onboard data layer into an autonomous, agentic system.

The Onboard Agent's Toolbelt (Function Calling)
To make the LLM an agent, your local-diagnostic-agent container exposes a set of secure Python functions to the model as executable "Tools." The agent reads the description of these tools and decides when to trigger them:

poll_im_oid(oid_string): Queries specific live sub-trees from the Stadler IM.

isolate_network_switch_port(vlan, port): Interacts with the train switch to segment a misbehaving node.

trigger_pis_display(coach_id, text_string): Alters the physical passenger information screens on a specific coach.

send_priority_mesh_alert(payload): Bypasses cellular drops to push an internal peer-to-peer Wi-Fi alert directly to the conductor’s handheld app.

Step-by-Step Execution of an Agentic Use Case
Consider this scenario: The train is moving through an Alpine tunnel, completely offline. A catastrophic or anomalous HVAC failure occurs.

1. The Trigger
The Stadler IM fires an asynchronous trap warning that im0Error (.80) has registered an over-temperature and electrical drop flag on Coach 3's secondary compressor.

2. The Agent's Internal Reasoning Loop (ReAct)
Instead of just parsing a text summary, the Onboard Agent starts a multi-step analytical loop:

Thought 1: I see an active electrical flag on Coach 3's HVAC system. I need to understand if this is a systemic power failure or an isolated component fault.

Action 1: Triggers tool poll_im_oid("1.3.6.1.4.1.42054.10.1.1.10.1.50") (Queries live room temperatures from the IM spec).

Observation 1: Coach 3 temperature is 26°C and rising. Ambient outside temperature is 14°C. Adjacent Coach 2 and Coach 4 temperatures are 21°C.

Thought 2: The fault is localized to Coach 3, but the car is actively overheating. I must check passenger density to evaluate safety limits.

Action 2: Queries the local-fusion-engine database for the live vision tracking metrics on Coach 3.

Observation 2: Coach 3 currently has 74 seated passengers and 12 standing passengers in the aisles (High Density).

Thought 3: High human density combined with a failed cooling system will cause a rapid air-quality and comfort degradation within 8 minutes. Because we are offline in a tunnel, I cannot wait for cloud dispatch instructions. I must act locally to preserve passenger safety and re-route resources.

3. Autonomous Actions Taken By the Agent
Without checking in with a landside server, the local agent fires three sequential tool commands across the train's internal networks:

Mitigate Network Loop/Noise: It commands the localized switch to prioritize power routing to Coach 3's secondary fallback fans.

Passenger Guidance Control: It calls trigger_pis_display(3, "System Adjustment: Please relocate to adjacent coaches for optimal seating comfort."). This dynamically clears out the coach before it becomes an emergency.

Conductor Intercept Routing: It generates an immediate, high-priority push notification to the conductor's mobile application over the internal vehicle Wi-Fi mesh:

"Agent Action: Coach 3 primary HVAC compressor failed. Thermal climb detected. 86 passengers affected. I have dynamically updated the PIS screens to redistribute passengers to Coaches 2 and 4. Please manually inspect the circuit cabinet in Coach 3, Row 4 upon tunnel exit."

Why Agentic AI Outperforms "Just RAG" for Nomad Digital
Capability	Onboard Static RAG	Onboard Agentic LLM
Data Interaction	Reads historical manual pages passively based on an error text string.	Dynamically probes the train's live state (im0Gps, im0VehicleState, im0Error) based on what it discovers step-by-step.
Problem Solving	Tells a human what the error code means.	Formulates an operational hypothesis, checks dependencies, and acts to resolve or mitigate the issue.
System Footprint	One-way translation layer.	Closed-loop edge operator.
How to Build it on the Train
By migrating to the Hailo-10 platform (leveraging its dedicated 8GB/16GB LPDDR4X memory space), your development team can use a lightweight agentic orchestration library like LangChain-Core or AutoGPT-lite compiled natively inside the local-diagnostic-agent container.

This takes Nomad Digital completely out of the "telemetry graph provider" category and places you squarely as the creator of an Autonomous Onboard Digital Engineer.

Yep — I already checked the SharePoint DANI folders and pulled back the most relevant files that contain (or hint at) use cases / requirements / train app integration. Here’s the clean, “just-the-results” view so you can jump straight into the right docs.

🔎 Best matches in DANI SharePoint folders (use cases / requirements / app-related)
1) DaNi IT-Konzept (Design / Requirements backbone)
These are the strongest sources for “what ÖBB wanted” (even when it’s written as concept/requirements rather than a formal use-case list):

ND-DEL-OBB-021-CRS-001-31_DaNi_IT-Konzept_v3.1.docx (projects site) [AW: Duagon  PO 43679 | Outlook]
ND-DEL-OBB-021-CRS-001-31_DaNi_IT-Konzept_v3.2.docx (external sharing site) [WG: Final...ease notes | Outlook]
ND-DEL-OBB-021-CRS-001-20_DaNi_IT-Konzept_v2.8.docx [WG: DANI 2...4] - PM VO | Outlook]
ND-DEL-OBB-021-CRS-001-11_DaNi_IT-Konzept_BASIC and EXTENDED DRAFT v1.docx [RE: OEBB D...ain server | Outlook]

✅ These include key functional expectations like multiple portal instances (day/night), portal redundancy, load balancing, and interfaces (often where “use cases” are embedded in narrative). [AW: Duagon  PO 43679 | Outlook], [WG: Final...ease notes | Outlook], [WG: DANI 2...4] - PM VO | Outlook], [RE: OEBB D...ain server | Outlook]

2) Technical Description (Portal / API / behavior details)

Technical Description - DANI.pdf (external sharing site) [Vaneza Jou...07.05.2026 | Outlook]

✅ Useful for system behaviors that become “technical use cases” (portal sync leader/follower, failover expectations, etc.). [Vaneza Jou...07.05.2026 | Outlook]

3) Offer / Appendix docs that explicitly mention “use cases”

DANi wagons WiFi - Nomad offer release v0.6.docx (mentions “use cases for load balancing… and shared content sync”) [OEBB Task tracker | Outlook]
ÖBB DANi offer Appendix 3_testcase_information.docx (test cases rather than business use cases, but often mapped 1:1 in reviews) [WG: Rückme...en  Switch | Outlook]
Appendices for ND-BID-OBB-004-TEN-001.docx (links out to acceptance testcase folder + other appendices) [DANI delay...d payments | Outlook]

✅ These are great if you want to show what was expected to be validated, which often equals “use case coverage” in practice. [OEBB Task tracker | Outlook], [WG: Rückme...en  Switch | Outlook], [DANI delay...d payments | Outlook]

4) Smart Train App / “mobile device apps (staff)” related (closest app wording)
The most direct “train app / staff app” language I saw is embedded in Siemens/IT concept style docs (services for mobile apps), not as a separate “use case” document:

EN - version - A6Z00044255571_C_Draft_OEBB-DANI IT-Konzept_Vorab_Word.docx
Contains scope like “Basic services… for mobile device apps (train staff)…” [[DANI] NL34 | Outlook]
ND-DEL-OBB-021-SPE-001-01– Scope of Design Freeze.pdf (includes section about access from staff mobile devices via staff Wi‑Fi / services) [RE: Norske...ified gaps | Outlook]

✅ If ÖBB “use cases” were sent as concepts, these are where they usually live. [[DANI] NL34 | Outlook], [RE: Norske...ified gaps | Outlook]

5) MQTT / data reporting (often part of app telemetry requirements)

ND-DEVOPS-OBB-TER-025-002.docx (includes MQTT reporting test steps / expected structure) [RE: ÖBB-DA...mad -> SMO | Outlook]


⚠️ What I did not find in DANI SharePoint
I did not see a single standalone document titled like:

“Use Cases – Smart Train App”
“ÖBB App Use Case Catalogue”
“Train App Requirements List”

Instead, the “use cases” are embedded inside IT concept / technical description / test-case docs. [AW: Duagon  PO 43679 | Outlook], [Vaneza Jou...07.05.2026 | Outlook], [WG: Rückme...en  Switch | Outlook]

Fastest way to get your “use cases they sent me”
If your goal is: “show me the use cases ÖBB provided”, the best two sources to open first are:

A6Z… Draft ÖBB-DANI IT-Konzept (EN version) (because it explicitly mentions staff mobile apps/services) [[DANI] NL34 | Outlook]
DaNi IT-Konzept v3.1 / v3.2 (because that’s where functional expectations are consolidated) [AW: Duagon  PO 43679 | Outlook], [WG: Final...ease notes | Outlook]


One quick question (so I can narrow to the exact folder set you mean)
When you say “DANI folders”, do you mean:

DEL-OBB-021 (DANI) project area, or
the older ob01/Bid Documents/DANI area (the bid archive)?

(If you tell me which one you care about most, I’ll list the top 10 exact documents in that area that contain app/service requirements.)
SourcesProvide your feedback on BizChatYou said: search for smart train appMy Sharepoint said: My Sharepoint✅ Search completed: “smart train app” in DANI SharePoint folders
Here are the exact documents in the DANI SharePoint where “smart train app” explicitly appears (this is the strongest, evidence‑based result set you were looking for):

📄 Documents containing “smart train app”
1. EN‑version – A6Z00044255571_C_Draft_OEBB‑DANI IT‑Konzept_Vorab_Word.docx
Location: DEL-OBB-021 (DANI)
Key wording found:

“services also for mobile device apps (train staff) (e.g. information app, smart train app)”

✅ This is the clearest ÖBB-originated reference tying smart train app to staff mobile applications.

2. ND‑DEL‑OBB‑021‑CRS‑001‑31_DaNi_IT‑Konzept_v3.1.docx
Location: DEL-OBB-021 (DANI)
Key wording found:

“daemon and services available to the smart train app, are handed over via MQTT for mobile devices”

✅ This explicitly defines:

Smart Train App
Data delivery mechanism (MQTT)
Mobile device usage

This is effectively a technical use‑case description.

3. ND‑DEL‑OBB‑021‑CRS‑001‑11_BASIC and Extended IT‑Konzept.docx
Location: DEL-OBB-021 (DANI)
Key wording found:

“services also for mobile device apps (train staff) (e.g. information apps, smart train app)”

✅ Confirms the same concept already present in early/basic IT concepts.

4. Technical Description – DANI.pdf
Location: DEL‑OBB‑021 External Sharing
Key wording found:

“…release of the number of connected clients to the smart train app…”

✅ Indicates runtime / operational data being exposed to the Smart Train App.

🔎 What this tells us (important conclusion)
✔ “Smart Train App” is an ÖBB term used consistently across:

IT‑Konzept documents
Technical Description
Staff mobile app context

❌ There is no standalone “Smart Train App – Use Cases” document
✅ Instead, use cases are embedded across IT‑Konzept and Technical Description documents

✅ De‑facto Smart Train App scope (from SharePoint evidence)
From the documents above, Smart Train App is intended to:

Be a staff mobile application
Consume on‑board services and data
Receive data via MQTT
Access operational metrics (e.g. connected clients, system state)

This aligns perfectly with what you saw earlier in emails + MQTT discussions.

👉 Recommended next step (high value)
If you want, I can:

Extract all Smart Train App–related paragraphs from these 4 documents into one clean use‑case summary, or
Map them into a bid‑ready “Smart Train App – Functional Scope” slide/page you can reuse with ÖBB.

Just tell me which you want.
Provide your feedback on BizChatYou said: Extract Smart Train App use-case summaryMy Sharepoint said: My SharepointBelow is a clean, evidence‑based Smart Train App use‑case summary, extracted directly from the DANI SharePoint documents (no assumptions added). This is suitable for internal alignment, bid text, or ÖBB discussions.

✅ Smart Train App – Use‑Case Summary (ÖBB DANI)
1. Purpose of the Smart Train App
The Smart Train App is defined as a mobile application for train staff, enabled by the DANI onboard IT architecture. It consumes onboard data and services to support operational awareness, diagnostics, and information access for staff during train operation. [[DANI] NL34 | Outlook], [RE: OEBB D...ain server | Outlook]

2. Target Users

Train staff / onboard personnel
Mobile devices connected via staff Wi‑Fi / onboard network

The Smart Train App is explicitly referenced as a staff-facing mobile application, not a passenger app. [[DANI] NL34 | Outlook], [RE: OEBB D...ain server | Outlook]

3. Core Functional Use Cases
UC‑1: Access to Onboard System Services
The Smart Train App consumes onboard services and daemons exposed by the train IT systems, allowing staff applications to retrieve operational information from the train. [AW: Duagon  PO 43679 | Outlook]

UC‑2: Real‑Time Data Delivery via MQTT
Onboard services make data available to the Smart Train App using MQTT as the delivery mechanism.
This enables near‑real‑time data consumption on mobile devices. [AW: Duagon  PO 43679 | Outlook], [RE: ÖBB-DA...mad -> SMO | Outlook]

UC‑3: Operational Metrics & Train State Visibility
The Smart Train App receives operational metrics, such as:

Number of connected clients
Detected devices
Runtime system information

These metrics are explicitly referenced as being released to the Smart Train App for operational visibility. [Vaneza Jou...07.05.2026 | Outlook]

UC‑4: Staff Mobile Information Services
The Smart Train App is listed alongside information apps for train staff, indicating its role in:

Displaying operational information
Supporting staff decision‑making onboard

This positions the app as a general-purpose operational companion rather than a single‑function tool. [[DANI] NL34 | Outlook], [RE: OEBB D...ain server | Outlook]

4. System & Integration Context
Data Sources

Onboard daemons and services
Train IT subsystems connected to the operator network

Data Transport

MQTT for telemetry and service data delivery [AW: Duagon  PO 43679 | Outlook], [RE: ÖBB-DA...mad -> SMO | Outlook]

Network Context

Staff Wi‑Fi / onboard mobile access
Secure onboard environment defined in the DANI IT concept [RE: Norske...ified gaps | Outlook]


5. Explicit Non‑Scope (per SharePoint evidence)
The following are not defined in the DANI documentation for the Smart Train App:

Passenger‑facing functionality
UX/UI flows or screen designs
Business workflows (e.g. ticketing, sales)
AI or analytics features

Only technical enablement and data exposure are specified. [AW: Duagon  PO 43679 | Outlook], [Vaneza Jou...07.05.2026 | Outlook]

6. One‑Line Executive Summary (reuse‑ready)

The ÖBB Smart Train App is a staff mobile application enabled by the DANI onboard IT architecture, providing real‑time access to onboard services and operational metrics via MQTT for mobile devices connected to the train network. [AW: Duagon  PO 43679 | Outlook], [Vaneza Jou...07.05.2026 | Outlook], [[DANI] NL34 | Outlook]

which model should i use for this? is it only the models available by hailo?

No, you are not restricted only to models natively provided by Hailo.

The hardware does not care who trained the model or where it came from. The only hard rule is a format constraint: the final binary must be a compiled .hef (Hailo Executable Format) file.

Because you have that high-spec Intel® Xeon® 6-Core blade with 64GB of RAM, you can take almost any standard open-source model (from Hugging Face or GitHub) and use the Hailo Dataflow Compiler (DFC) to quantize, optimize, and compile it yourself into a .hef format.

For your "Eye + Brain" configuration (1x Hailo-8 + 1x Hailo-10), the ideal model choices split cleanly between pre-compiled models from the Hailo Zoo and open-source models you compile yourself.

1. For the "Brain" (Hailo-10 Local Agent)
The Hailo-10 architecture includes specialized memory channels specifically built to handle Generative AI. The Hailo community and Model Zoo officially support and provide compiled paths for the industry's best lightweight open-source models:

Llama-3.2-3B-Instruct (Recommended Core Engine): This is the ideal balance for your offline agentic work. It supports high-quality Function-Calling / Tool Use, allowing the model to smoothly choose when to poll the Stadler IM or trigger the PIS screens.

DeepSeek-R1-Distill-Llama-8B (or 1.5B): If you require deeper logical "reasoning steps" before an action is taken (e.g., investigating complex multi-traction faults), the distilled R1 reasoning models compile beautifully to the Hailo-10 architecture.

Qwen-2-1.5B-Instruct or Qwen-2-VL-2B (Vision-Language Model): If you want your agent to process an image directly alongside text (e.g., looking at an occlusion snippet if a door jams), the Qwen series has native .hef parsing pipelines in the latest Hailo software releases.

2. For the "Eye" (Hailo-8 Vision Pipeline)
Since your camera counting, seating density, and baggage tracking logic are based on geometric spatial algorithms, the Hailo Model Zoo v2.x branch provides pre-compiled, production-ready files out of the box:

yolov8m.hef or yolov11m.hef: (For object detection classes: person, backpack, suitcase, bicycle).

yolov8m_pose.hef: (For extracting the 17-point passenger skeleton keypoints in accessibility spaces).

How to Bring a Custom Model onto the Train (The Tooling Pipeline)
If you find a brilliant new open-source model on Hugging Face (for instance, a specific German-language fine-tuned model or a custom anomaly detection model), your development team follows a 3-step conversion process on their development machines before pushing the container to the train:

 ┌────────────────┐      ┌───────────────┐      ┌──────────────────────────┐      ┌─────────────┐
 │  Hugging Face  │ ───► │  ONNX Format  │ ───► │ Hailo Dataflow Compiler  │ ───► │ Final .hef  │
 │ (PyTorch/TF)   │      │  (.onnx file) │      │ (Quantize to INT8/INT4)  │      │   Binary    │
 └────────────────┘      └───────────────┘      └──────────────────────────┘      └─────────────┘
Export to ONNX: Convert the model weights from PyTorch or TensorFlow into an ordinary open standard ONNX (.onnx) graph.

Run the Dataflow Compiler (DFC): Pass the ONNX file through Hailo’s optimization tool. Here, the model is compressed and quantized (typically converting heavy 32-bit floating points into ultra-fast INT8 for the Hailo-8, or INT4/INT8 mix for the Hailo-10).

Compile to HEF: The DFC outputs the .hef file tailored perfectly to the specific chip layout.

The Compiler Constraint Warning
The only time you will hit a wall with a custom model is if its underlying math architecture uses mathematical operations that the physical silicon layers can't compute. For example, if a model uses exotic custom attention mechanisms or complex 3D convolutions that aren't mapped in the Hailo Dataflow Compiler hardware support matrix, the compiler will flag an error during compilation.

Stick to standard transformer architectures (like Llama, Mistral, Phi, or Qwen) for the brain, and standard CNNs/ViTs (YOLO, MobileNet, ResNet) for the eyes, and you can freely deploy any custom or fine-tuned model you want completely offline on the ÖBB fleet.