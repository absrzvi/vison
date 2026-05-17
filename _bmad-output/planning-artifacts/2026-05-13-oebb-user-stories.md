# OEBB Smart Rail — User Stories
**Date:** 2026-05-13
**Status:** Complete — 35 use cases · 8 personas · 57 user stories
**Related specs:** `2026-05-13-oebb-hailo8-ai-service-design.md` · `2026-05-13-oebb-ux-design.md`

---

## Personas

| # | Persona | Device | Primary AI service |
|---|---|---|---|
| 1 | Conductor / Train Manager | Mobile handheld | Both |
| 2 | Onboard Technician | Mobile handheld | Diagnostics AI |
| 3 | Bistro / Café Staff | Tablet or handheld | Passenger AI |
| 4 | Driver | Cab-mounted display | Both (display only) |
| 5 | Control Centre Operator | Web dashboard | Both |
| 6 | Fleet Maintenance Manager | Web dashboard | Diagnostics AI + occupancy |
| 7 | Capacity Planner | Web reports | Passenger AI analytics |
| 8 | Platform Staff / Station Manager | Tablet or display | Passenger AI |

---

## Conductor / Train Manager

**UC-01 — Passenger counting**
As a conductor, I want to see the live headcount in each coach so that I can redistribute passengers away from overcrowded areas before the train departs.

**UC-02 — Luggage counting**
As a conductor, I want to know how many luggage items are in each coach so that I can proactively manage overhead rack space and avoid delays at busy stops.

**UC-03 — Congestion mapping**
As a conductor, I want a colour-coded train diagram showing which coaches are full, filling, and empty so that I can direct boarding passengers to the right carriage without walking the full length of the train.

**UC-04 — Unattended luggage detection**
As a conductor, I want an alert when a bag has been left unattended for more than a configurable time so that I can investigate promptly and avoid a security incident.

**UC-05 — Door obstruction detection**
As a conductor, I want to be notified when a passenger or bag is blocking a door so that I can clear the obstruction and prevent a delayed departure.

**UC-06 — Stadler + TCMS alarm ingestion**
As a conductor, I want to see active train subsystem alarms in plain language alongside my passenger alerts so that I have a single view of everything happening on the train without needing a separate diagnostics tool.

**UC-07 — Door alarm cross-correlation**
As a conductor, I want a high-priority alert when both the camera and the door fault sensor agree there is a door problem so that I can distinguish a real safety incident from a sensor glitch and act with confidence.

**UC-17 — Passenger guidance display**
As a conductor, I want the passenger-facing portal to automatically show coach load so that passengers self-distribute before boarding and I spend less time directing people manually.

**UC-19 — Accessibility assistance detection**
As a conductor, I want to be alerted when a wheelchair user or pushchair is detected onboard so that I can ensure the right coach door is used and the ramp is deployed in time.

**UC-27 — Speed-correlated door fault**
As a conductor, I want door fault alerts to be flagged as higher severity when the train is in motion so that I can distinguish an in-service safety risk from a platform-stop sensor anomaly.

**UC-28 — Maintenance mode suppression**
As a conductor, I want AI alerts to be suppressed when the train is in depot maintenance mode so that I am not distracted by false alarms during shunting or servicing.

**UC-32 — PRM door + camera correlation**
As a conductor, I want to be notified when the accessibility door is released and a wheelchair user is detected nearby so that I can be at the right door at the right moment.

**UC-33 — Wheelchair ramp deployed → platform alert**
As a conductor, I want an alert when the wheelchair ramp is deployed so that I can coordinate with platform staff at the next stop to have assistance ready.

---

## Onboard Technician

**UC-06 — Stadler + TCMS alarm ingestion**
As an onboard technician, I want to see all active Stadler and TCMS alarms in a structured log with AI annotations so that I can understand what the alarm code actually means without looking it up in a manual.

**UC-09 — Diagnostics AI — fault pattern detection**
As an onboard technician, I want the system to flag when an alarm is recurring or matching a known fault pattern so that I can prioritise it over one-off transient alarms.

**UC-10 — Predictive fault alerting**
As an onboard technician, I want to be told when a fault pattern suggests a subsystem is likely to fail within a specific time window so that I can plan a depot intervention before it becomes a service-affecting breakdown.

**UC-16 — Natural language diagnostics agent**
As an onboard technician, I want to ask the system "is it safe to continue to the next city?" and get an answer that cites the specific alarms and fleet history it used so that I can make an informed go/no-go decision and explain it to the driver.

**UC-27 — Speed-correlated door fault**
As an onboard technician, I want door faults at speed to be escalated automatically so that I am aware of safety-critical events even if I am working in a different part of the train.

**UC-29 — Degraded operation alert**
As an onboard technician, I want an immediate alert when the train enters degraded operation mode so that I can assess which redundant systems have taken over and whether intervention is needed.

**UC-34 — Odometer-based maintenance scheduling**
As an onboard technician, I want to see the current odometer reading alongside any active alarms so that I can judge whether a fault is correlated with a known mileage threshold.

---

## Bistro / Café Staff

**UC-20 — Bistro demand intelligence (demand indicator)**
As a bistro staff member, I want to see whether demand is HIGH, MEDIUM, or LOW for the next 30 minutes so that I can decide whether to call a colleague to help or manage the counter alone.

**UC-20 — Bistro demand intelligence (footfall trend)**
As a bistro staff member, I want to see a sparkline of passengers passing through the bistro area in the last 30 minutes so that I can tell whether demand is rising or has already peaked.

**UC-20 — Bistro demand intelligence (queue count)**
As a bistro staff member, I want to see a live count of people queuing at the counter so that I can open a second serving position before the queue gets too long.

**UC-20 — Bistro demand intelligence (coach load direction)**
As a bistro staff member, I want to see which coaches are heavily loaded and sending passengers toward the bistro car so that I can anticipate a rush before it arrives.

**UC-20 — Bistro demand intelligence (stock alert)**
As a bistro staff member, I want the system to tell me which items to restock at the next depot stop, based on current stock levels and predicted demand, so that I do not run out of coffee or food mid-journey.

**UC-22 — Boarding volume prediction**
As a bistro staff member, I want to know how many passengers are expected to board at each upcoming stop so that I can prepare enough product and staffing before each arrival.

---

## Driver

**UC-05 — Door obstruction detection**
As a driver, I want a clear visual indicator on my cab display when any door is obstructed so that I do not depart with a passenger or bag caught in a door.

**UC-06 — Stadler + TCMS alarm ingestion**
As a driver, I want to see only critical-severity faults on my display so that I am not distracted by minor warnings that the conductor or technician should handle.

**UC-22 — Boarding volume prediction / platform congestion**
As a driver, I want an advisory on my display when the next platform is predicted to be heavily congested so that I can hold the doors open longer or notify the conductor in advance.

**UC-27 — Speed-correlated door fault**
As a driver, I want door fault alerts to appear on my display when the train is in motion so that I can stop the train if there is a genuine door safety issue.

---

## Control Centre Operator

**UC-08 — Operations dashboard & alerting**
As a control centre operator, I want a live fleet view showing occupancy, active incidents, and fault alerts across all trains so that I can identify which train needs intervention without waiting for a radio call.

**UC-08 — Operations dashboard (unified incident feed)**
As a control centre operator, I want a single prioritised feed of passenger and diagnostics events across the whole fleet so that the most critical incident is always at the top, regardless of which train or AI system generated it.

**UC-11 — Dwell time analysis**
As a control centre operator, I want to see real-time dwell times at each stop so that I can identify when a boarding delay is about to cascade into a timetable disruption and take proactive action.

**UC-12 — Predictive overcrowding**
As a control centre operator, I want to be warned when a specific coach is forecast to exceed capacity at an upcoming stop so that I can arrange additional services or divert passengers before the problem occurs.

**UC-14 — Slip/fall detection**
As a control centre operator, I want an immediate alert when a person-down event is detected on any train so that I can dispatch the correct response without waiting for a passenger to call it in.

**UC-15 — Prohibited zone detection**
As a control centre operator, I want an alert when someone enters a restricted area on any train so that I can instruct the conductor to intervene and log the incident.

**UC-29 — Degraded operation alert**
As a control centre operator, I want to be notified the moment any train enters degraded operation mode so that I can assess service impact and begin contingency planning.

**UC-35 — Trip-labelled data**
As a control centre operator, I want every incident to be tagged with the trip ID and route so that I can search historical incidents by journey for post-incident review.

---

## Fleet Maintenance Manager

**UC-09 — Diagnostics AI — fault pattern detection**
As a fleet maintenance manager, I want AI-generated work orders based on recurring fault patterns so that my team does not miss a developing fault that no individual alarm would surface alone.

**UC-10 — Predictive fault alerting**
As a fleet maintenance manager, I want to see which trains have predicted failures and their estimated time windows so that I can schedule depot visits before failures become service disruptions.

**UC-13 — Cleaning & maintenance triggers**
As a fleet maintenance manager, I want the system to auto-generate cleaning work orders when coach occupancy intensity exceeds thresholds so that I do not have to manually review journey logs to schedule cleaning.

**UC-25 — Energy efficiency reporting**
As a fleet maintenance manager, I want to see energy anomalies flagged against occupancy data so that I can tell whether high energy consumption is caused by passenger load or a malfunctioning subsystem.

**UC-29 — Degraded operation alert**
As a fleet maintenance manager, I want a log of every degraded operation event with the specific subsystems affected so that I can identify trains that are repeatedly falling back to redundant systems and prioritise them for inspection.

**UC-30 — Parking-triggered depot logic**
As a fleet maintenance manager, I want a maintenance window summary generated automatically when a train enters parking mode so that I can assign overnight work orders without manually reviewing the day's fault log.

**UC-31 — Energy mode awareness**
As a fleet maintenance manager, I want to know which trains are running in battery or energy saving mode and for how long so that I can flag unusual energy mode patterns as potential indicators of a charging or traction fault.

**UC-34 — Odometer-based maintenance scheduling**
As a fleet maintenance manager, I want the system to flag when a train is approaching a mileage-based inspection threshold so that I can schedule the inspection at the next suitable depot visit rather than reactively.

**UC-35 — Trip-labelled data**
As a fleet maintenance manager, I want all fault events labelled with trip IDs so that I can correlate recurring faults with specific routes, weather conditions, or driver behaviour.

---

## Capacity Planner

**UC-11 — Dwell time analysis**
As a capacity planner, I want monthly dwell time reports per stop so that I can identify chronic boarding bottlenecks and recommend infrastructure changes or additional rolling stock.

**UC-12 — Predictive overcrowding**
As a capacity planner, I want historical overcrowding forecasts compared against actuals so that I can validate the model and use it to inform timetable revision decisions.

**UC-21 — No-show seat detection**
As a capacity planner, I want data on reserved-but-empty seats by route, day type, and class so that I can quantify the revenue and capacity impact of no-shows and propose a yield management policy.

**UC-24 — Anonymised ridership analytics**
As a capacity planner, I want monthly reports on boardings, peak loads by route and time of day, and coach class occupancy so that I can make evidence-based decisions about fleet allocation and service frequency.

**UC-25 — Energy efficiency reporting**
As a capacity planner, I want occupancy-normalised energy KPIs per journey so that I can present accurate sustainability metrics to OEBB's ESG reporting function.

**UC-26 — Advertising audience metadata**
As a capacity planner, I want aggregate audience profiles per route so that I can make a data-backed case for advertising revenue on portal screens and price inventory appropriately.

**UC-35 — Trip-labelled data**
As a capacity planner, I want all occupancy data labelled with trip ID and route so that I can segment analysis by journey type, season, or event without needing to reconcile disparate data sources.

---

## Platform Staff / Station Manager

**UC-12 — Predictive overcrowding**
As a platform staff member, I want to see the coach-level occupancy of the incoming train before it arrives so that I can position passengers on the platform to board the least crowded coaches.

**UC-18 — Smart Travel API**
As a station manager, I want platform display screens to show incoming train coach load in real time so that passengers self-distribute on the platform without staff intervention.

**UC-19 — Accessibility assistance detection**
As a platform staff member, I want to know in advance if a wheelchair user or passenger needing assistance is on the incoming train, with their coach and door number, so that I can be in the right position when the train arrives.

**UC-22 — Boarding volume prediction**
As a platform staff member, I want a forecast of how many passengers will board at this station so that I can manage platform crowding and prepare for a long dwell if boarding volumes are high.

**UC-23 — PIS-synced guidance**
As a station manager, I want platform displays to automatically update when the PIS announces a platform change or delay so that passengers get consistent information across all screens without manual intervention.

**UC-33 — Wheelchair ramp deployed → platform alert**
As a platform staff member, I want an alert when the wheelchair ramp is deployed on an incoming train so that I can be at the exact door before the train stops.
