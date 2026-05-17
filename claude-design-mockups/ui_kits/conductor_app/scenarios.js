// Scenarios — drives the data shown across the app

window.SCENARIOS = {
  boarding: {
    label: "T−8 boarding",
    time: "09:42",
    nextStop: "Linz Hbf · 8 min",
    selectedCoach: 3,
    activeBanner: { tone: "warning", iconName: "alert-triangle", title: "Coach 3 — rack 94% full", sub: "Large boarding expected at Linz · 8 min" },
    coaches: [
      { num: 1, pct: 34 }, { num: 2, pct: 41 }, { num: 3, pct: 67 }, { num: 4, pct: 91 }, { num: 5, pct: 58 },
      { num: 6, pct: 29 }, { num: 7, pct: 22 }, { num: 8, pct: 18 }, { num: 9, pct: 15 }, { num: 10, pct: 12 },
    ],
    rackPct: 94,
    metrics: [
      { label: "Actual pax",  value: 98, sub: "counted by Hailo", tone: "critical" },
      { label: "Reserved",    value: 50, sub: "+48 overboard",    tone: "warning" },
      { label: "Luggage",     value: 7,  sub: "in vestibule" },
      { label: "Congestion",  value: 74, sub: "score / 100",      tone: "warning" },
      { label: "Bicycles",    value: 0,  sub: "detected",         tone: "ok" },
      { label: "Access.",     value: 1,  sub: "Door 1" },
    ],
    alerts: [
      { type: "fire", title: "Smoke detected — Coach 5", sub: "All parties alerted · Emergency protocol active", when: "NOW" },
      { type: "high", iconName: "construction", title: "Vandalism detected — Coach 6", sub: "Window area · Vandalism module", when: "3m ago" },
      { type: "medium", iconName: "bike", title: "Bicycle blocking door — Coach 3 D2L", sub: "Vestibule · Luggage/bicycle module", when: "1m ago" },
      { type: "warning", iconName: "package", title: "Rack saturation — Coach 3", sub: "94% · Large boarding at Linz", when: "2m ago" },
      { type: "fault", iconName: "thermometer", title: "HVAC alarm — Coach 3", sub: "Diagnostics AI · Low severity", when: "11m ago" },
      { type: "info", iconName: "accessibility", title: "Wheelchair user boarding", sub: "Coach 4 · Next stop: Linz Hbf", when: "Live" },
    ],
  },

  vestibule: {
    label: "Vestibule alert",
    time: "10:14",
    nextStop: "Linz Hbf · 12 min",
    selectedCoach: 4,
    activeBanner: { tone: "warning", iconName: "users", title: "Vestibule crowding — Coach 4", sub: "11 pax in door zone · 12 min to stop" },
    coaches: [
      { num: 1, pct: 38 }, { num: 2, pct: 44 }, { num: 3, pct: 62 }, { num: 4, pct: 85 }, { num: 5, pct: 53 },
      { num: 6, pct: 34 }, { num: 7, pct: 26 }, { num: 8, pct: 20 }, { num: 9, pct: 16 }, { num: 10, pct: 13 },
    ],
    rackPct: 71,
    heatmap: { coach: 4, badge: "11 pax bunching", badgeTone: "amber", note: "Passengers pre-positioning for stop 12 min away. Seats visible but unused toward coach centre.",
      rows: [
        { label: "Seats", labelTone: "ok",   density: "cool",    text: "Underused — 8 free seats visible", count: 3, countTone: "green" },
        { label: "Aisle", density: "warm-lo", text: "Moving through", count: 4, countTone: "amber" },
        { label: "Door",  density: "warm-hi", text: "Crowding building", count: 6, countTone: "amber" },
        { label: "Vstb",  labelTone: "alert", density: "hot",    text: "Dense — early queueing", count: 11, countTone: "red" },
      ],
    },
    paDraft: {
      title: "PA Announcement",
      scope: "Coach 4 only",
      text: "Passengers in coach 4 — the next stop is still 12 minutes away. Please move away from the doors and use available seating.",
    },
    alerts: [],
  },

  resolved: {
    label: "Vestibule resolved",
    time: "10:16",
    nextStop: "Linz Hbf · 10 min",
    selectedCoach: 4,
    activeBanner: { tone: "resolved", iconName: "check", title: "Vestibule cleared — Coach 4", sub: "Resolved via PA · 1 min 48 sec" },
    coaches: [
      { num: 1, pct: 38 }, { num: 2, pct: 44 }, { num: 3, pct: 60 }, { num: 4, pct: 68 }, { num: 5, pct: 53 },
      { num: 6, pct: 34 }, { num: 7, pct: 26 }, { num: 8, pct: 20 }, { num: 9, pct: 16 }, { num: 10, pct: 13 },
    ],
    rackPct: 66,
    heatmap: { coach: 4, badge: "Cleared", badgeTone: "green",  note: "Alert auto-resolved on sensor change — no manual close required.",
      rows: [
        { label: "Seats", labelTone: "ok", density: "warm-lo", text: "Passengers redistributed", count: 9, countTone: "amber" },
        { label: "Aisle", labelTone: "ok", density: "cool",    text: "Normal", count: 3, countTone: "green" },
        { label: "Door",  labelTone: "ok", density: "empty",   text: "Clear",  count: 1, countTone: "green" },
        { label: "Vstb",  labelTone: "ok", density: "empty",   text: "Clear",  count: 2, countTone: "green" },
      ],
    },
    summary: [
      { label: "Vestibule zone", value: "Clear (2 pax)", tone: "green" },
      { label: "Alert resolved", value: "Auto · 1m 48s", tone: "green" },
      { label: "PA sent",        value: "Coach 4 · 10:14" },
      { label: "Action logged",  value: "Resolved via PA" },
    ],
    alerts: [],
  },

  imbalance: {
    label: "Occupancy imbalance",
    time: "10:31",
    nextStop: "En route",
    selectedCoach: 1,
    activeBanner: { tone: "warning", iconName: "scale", title: "Occupancy imbalance detected", sub: "C1–4 avg 87% · C7–10 avg 31%" },
    coaches: [
      { num: 1, pct: 88 }, { num: 2, pct: 92 }, { num: 3, pct: 82 }, { num: 4, pct: 85 }, { num: 5, pct: 60 },
      { num: 6, pct: 55 }, { num: 7, pct: 32 }, { num: 8, pct: 30 }, { num: 9, pct: 31 }, { num: 10, pct: 28 },
    ],
    rackPct: 78,
    imbalance: {
      groups: [
        { label: "Coaches 1–4 (heavy)", pct: 87, tone: "red" },
        { label: "5–6 (mid)",           pct: 58, tone: "amber" },
        { label: "7–10 (light)",        pct: 31, tone: "green" },
      ],
      details: [
        { label: "Free seats — C8 & C9",        value: "38 available", tone: "green" },
        { label: "C10 reserved — no-show",      value: "4 seats",      tone: "amber" },
        { label: "Est. passengers to move",     value: "~14 pax" },
      ],
    },
    paDraft: {
      title: "PA + Interior Screens",
      scope: "Coaches 1–4",
      text: "Passengers in coaches 1 to 4 — coaches 8, 9 and 10 have plenty of available seating and are a short walk through the train.",
      submitLabel: "Announce + Screens",
    },
    pisPreview: { coachStates: ["r","r","a","a","e","e","g","g","g","g"], headline: "Coaches 8 – 10", subline: "38 seats available  →" },
    alerts: [],
  },

  bag: {
    label: "Unattended bag",
    time: "11:03",
    nextStop: "En route",
    selectedCoach: 6,
    activeBanner: { tone: "info", iconName: "eye", title: "Unattended item — Coach 6 vestibule", sub: "Stationary 7 min · Area now empty · Review required" },
    coaches: [
      { num: 1, pct: 42 }, { num: 2, pct: 48 }, { num: 3, pct: 55 }, { num: 4, pct: 60 }, { num: 5, pct: 38 },
      { num: 6, pct: 26 }, { num: 7, pct: 30 }, { num: 8, pct: 28 }, { num: 9, pct: 25 }, { num: 10, pct: 22 },
    ],
    rackPct: 41,
    camera: {
      label: "Camera Still — Coach 6 Vestibule",
      timestamp: "2026-05-14  11:03:22",
      coachTag: "C6 · VESTIBULE",
      meta: "Bag detected 10:56 · Area cleared 10:56",
      timer: "7 min stationary",
      note: "Medium backpack · Floor, door 2 area. Surrounding seats vacated 7 min ago. No person has returned.",
    },
    paDraft: {
      title: "PA — Owner Request",
      scope: "All coaches",
      text: "Attention passengers — has anyone left a bag in coach 6 near the doors? Please return to collect it immediately.",
      primaryLabel: "Send PA",
      secondaryLabel: "Escalate to Control",
      secondaryKind: "blue",
    },
    escalateNote: "Escalate sends this still-frame, coach location, and 7-min timer automatically to Claudia at Control Centre — no verbal description needed.",
    alerts: [],
  },
};

window.SCENARIO_ORDER = ["boarding", "vestibule", "resolved", "imbalance", "bag"];
