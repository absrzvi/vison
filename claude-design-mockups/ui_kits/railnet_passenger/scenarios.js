// 8 passenger-portal states from the spec
// Coach occupancy thresholds (consistent across all ÖBB Smart Rail surfaces):
//   green   0–60 %   Viel Platz
//   amber  61–85 %   Mäßig besetzt
//   orange 86–100 %  Stark besetzt
//   red    >100 %    Überfüllt

window.STATE_ORDER = [
  "mixed", "directed", "full",
  "access_free", "access_occupied", "ramp_ready",
  "mid_journey", "luggage_steer",
  "stale", "no_data",
];

window.STATE_META = {
  mixed:          { label: "Gemischte Auslastung",     uc: "UC-P01" },
  directed:       { label: "Empfehlung",               uc: "UC-P02" },
  full:           { label: "Zug stark besetzt",        uc: "UC-P03" },
  mid_journey:    { label: "Während der Fahrt",        uc: "UC-P04" },
  luggage_steer:  { label: "Gepäck-Hinweis",           uc: "UC-P05" },
  access_free:    { label: "Rollstuhlplatz frei",      uc: "UC-A01" },
  access_occupied:{ label: "Rollstuhlplatz belegt",    uc: "UC-A02" },
  ramp_ready:     { label: "Rampe bereit ✓",           uc: "UC-A05" },
  stale:          { label: "Daten veraltet",           uc: "fallback" },
  no_data:        { label: "Keine Daten",              uc: "fallback" },
};

window.STATES = {
  // ─────────────────────────────────────────────────────────────
  // UC-P01 — Mixed load, no clear best coach. Show colours only.
  // ─────────────────────────────────────────────────────────────
  mixed: {
    coaches: [
      { n: 1, pct: 45 }, { n: 2, pct: 72 }, { n: 3, pct: 38 }, { n: 4, pct: 80 },
      { n: 5, pct: 55 }, { n: 6, pct: 68 }, { n: 7, pct: 42 }, { n: 8, pct: 60 },
    ],
    freshness: "Vor 8 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // UC-P02 — One coach clearly best. Arrow + recommendation.
  // ─────────────────────────────────────────────────────────────
  directed: {
    coaches: [
      { n: 1, pct: 88 }, { n: 2, pct: 92 }, { n: 3, pct: 85 }, { n: 4, pct: 90 },
      { n: 5, pct: 32, luggage: true }, { n: 6, pct: 28, recommended: true },
      { n: 7, pct: 35 }, { n: 8, pct: 87 },
    ],
    guidance: {
      tone: "recommend",
      direction: "right",
      primary: "Gehen Sie zu Wagen 6",
      sub: "Viel Platz · Gepäckfach frei",
      platformHint: "Nach rechts am Bahnsteig",
    },
    freshness: "Vor 4 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // UC-P03 — Whole train very full. Least-worst.
  // ─────────────────────────────────────────────────────────────
  full: {
    coaches: [
      { n: 1, pct: 95 }, { n: 2, pct: 102 }, { n: 3, pct: 88, recommended: true },
      { n: 4, pct: 97 }, { n: 5, pct: 91 }, { n: 6, pct: 98 }, { n: 7, pct: 86 }, { n: 8, pct: 94 },
    ],
    guidance: {
      tone: "warn",
      primary: "Zug stark besetzt",
      sub: "Wagen 3 am wenigsten voll",
    },
    freshness: "Vor 12 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // UC-P04 — Already aboard, mid-journey. Reposition guidance.
  // ─────────────────────────────────────────────────────────────
  mid_journey: {
    coaches: [
      { n: 1, pct: 78, here: true }, { n: 2, pct: 84 }, { n: 3, pct: 70 },
      { n: 4, pct: 62 }, { n: 5, pct: 41, recommended: true }, { n: 6, pct: 48 },
      { n: 7, pct: 35 }, { n: 8, pct: 28 },
    ],
    guidance: {
      tone: "info",
      direction: "right",
      primary: "Mehr Platz in Wagen 5–8",
      sub: "Sie befinden sich in Wagen 1 · Umsteigen jederzeit möglich",
    },
    freshness: "Vor 6 Sek.",
    midJourney: true,
  },

  // ─────────────────────────────────────────────────────────────
  // UC-P05 — Steer to a coach with rack space, even if not least full.
  // ─────────────────────────────────────────────────────────────
  luggage_steer: {
    coaches: [
      { n: 1, pct: 55 }, { n: 2, pct: 48, luggage: true }, { n: 3, pct: 42, luggage: true },
      { n: 4, pct: 38, recommended: true }, { n: 5, pct: 52 }, { n: 6, pct: 60 },
      { n: 7, pct: 64 }, { n: 8, pct: 58 },
    ],
    guidance: {
      tone: "recommend",
      direction: "right",
      primary: "Wagen 4 für Gepäck empfohlen",
      sub: "Wagen 2 & 3 — Gepäckfächer fast voll",
    },
    freshness: "Vor 5 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // UC-A01 — Accessible space free. Ramp preparing. Conrad alert fired.
  // ─────────────────────────────────────────────────────────────
  access_free: {
    coaches: [
      { n: 1, pct: 45 }, { n: 2, pct: 38, prm: "free", recommended: true },
      { n: 3, pct: 60 }, { n: 4, pct: 72 }, { n: 5, pct: 55 }, { n: 6, pct: 48 },
      { n: 7, pct: 65 }, { n: 8, pct: 50 },
    ],
    access: {
      tone: "free",
      status: "Rollstuhlplatz frei",
      detail: "Wagen 2 · Tür 1",
      ramp: { state: "preparing", text: "Rampe wird vorbereitet …" },
      conradAlert: true,
    },
    freshness: "Vor 3 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // UC-A02 — Accessible space occupied. Contact conductor.
  // ─────────────────────────────────────────────────────────────
  access_occupied: {
    coaches: [
      { n: 1, pct: 45 }, { n: 2, pct: 88, prm: "occupied" }, { n: 3, pct: 60 },
      { n: 4, pct: 72 }, { n: 5, pct: 55 }, { n: 6, pct: 48 },
      { n: 7, pct: 65 }, { n: 8, pct: 50 },
    ],
    access: {
      tone: "occupied",
      status: "Rollstuhlplatz belegt",
      detail: "Wagen 2 · Tür 1",
      action: "Bitte Schaffner kontaktieren",
    },
    freshness: "Vor 11 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // UC-A05 — Conrad confirms ramp deployed. Live update.
  // ─────────────────────────────────────────────────────────────
  ramp_ready: {
    coaches: [
      { n: 1, pct: 45 }, { n: 2, pct: 38, prm: "free", recommended: true },
      { n: 3, pct: 60 }, { n: 4, pct: 72 }, { n: 5, pct: 55 }, { n: 6, pct: 48 },
      { n: 7, pct: 65 }, { n: 8, pct: 50 },
    ],
    access: {
      tone: "free",
      status: "Rollstuhlplatz frei",
      detail: "Wagen 2 · Tür 1",
      ramp: { state: "ready", text: "Rampe bereit" },
      conradAlert: true,
    },
    freshness: "Vor 2 Sek.",
  },

  // ─────────────────────────────────────────────────────────────
  // FALLBACK — Stale (>60s since last update).
  // ─────────────────────────────────────────────────────────────
  stale: {
    coaches: [
      { n: 1, pct: 45 }, { n: 2, pct: 72 }, { n: 3, pct: 38 }, { n: 4, pct: 80 },
      { n: 5, pct: 55 }, { n: 6, pct: 68 }, { n: 7, pct: 42 }, { n: 8, pct: 60 },
    ],
    stale: true,
    freshness: "Daten veraltet",
  },

  // ─────────────────────────────────────────────────────────────
  // FALLBACK — Hailo offline / API >2s timeout.
  // ─────────────────────────────────────────────────────────────
  no_data: {
    coaches: [],
    noData: true,
    freshness: "—",
  },
};
