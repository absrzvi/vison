// Occupancy thresholds (matches the spec exactly)
const TONES = {
  low:  { bg: "#22C55E", text: "Viel Platz" },        // 0–60
  mid:  { bg: "#F5A623", text: "Mäßig besetzt" },     // 61–85
  high: { bg: "#FF6B00", text: "Stark besetzt" },     // 86–100
  crit: { bg: "#FF3B3B", text: "Überfüllt" },         // >100
};
function toneFor(pct) {
  if (pct > 100) return "crit";
  if (pct > 85)  return "high";
  if (pct > 60)  return "mid";
  return "low";
}
window.toneFor = toneFor;
window.TONES = TONES;

// ─── LiveDot ─────────────────────────────────────────────────────
function LiveDot({ color = "#22C55E", animate = true }) {
  return (
    <span style={{
      width: 6, height: 6, borderRadius: "50%",
      background: color,
      display: "inline-block",
      animation: animate ? "rn-liveblink 1.5s ease-in-out infinite" : "none",
    }} />
  );
}

// ─── FreshnessPill ──────────────────────────────────────────────
function FreshnessPill({ text, stale, noData }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      fontSize: 10, fontWeight: 600,
      color: noData ? "var(--obb-mute)" : stale ? "#C9871F" : "var(--obb-silver)",
    }}>
      <LiveDot color={noData ? "#B8B9BA" : stale ? "#F5A623" : "#22C55E"} animate={!stale && !noData} />
      {text}
    </span>
  );
}

// ─── CoachDiagram ────────────────────────────────────────────────
function CoachDiagram({ coaches, dimmed }) {
  return (
    <div style={{
      display: "flex", gap: 4,
      opacity: dimmed ? 0.5 : 1,
      transition: "opacity .3s var(--ease-out)",
    }}>
      {coaches.map(c => <CoachBlock key={c.n} c={c} />)}
    </div>
  );
}

function CoachBlock({ c }) {
  const tone = toneFor(c.pct);
  const t = TONES[tone];
  const isRec = c.recommended;
  return (
    <div
      title={`Wagen ${c.n} — ${t.text} (${Math.min(c.pct, 100)}%)`}
      style={{
        flex: 1, height: 44, borderRadius: 6,
        background: t.bg,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        position: "relative",
        boxShadow: isRec ? "0 0 0 2px #fff, 0 0 0 4px var(--obb-red), 0 0 12px rgba(226,0,42,.35)" : "none",
        animation: isRec ? "rn-pulse-rec 2.2s ease-in-out infinite" : "none",
      }}>
      <span style={{ fontSize: 11, fontWeight: 800, color: "#fff", lineHeight: 1, letterSpacing: "-.01em" }}>{c.n}</span>
      <span style={{ fontSize: 9, fontWeight: 700, color: "rgba(255,255,255,.85)", marginTop: 1 }}>{Math.min(c.pct, 100)}%</span>
      {/* indicator icons in corners */}
      {c.luggage && (
        <span style={{ position: "absolute", top: 3, right: 3, background: "rgba(0,0,0,.18)", borderRadius: 3, padding: 1 }}>
          <Icon name="briefcase" size={9} color="#fff" stroke={2.6} />
        </span>
      )}
      {c.prm && (
        <span style={{
          position: "absolute", bottom: -2, right: -2,
          background: c.prm === "occupied" ? "#F5A623" : "#4A9EFF",
          borderRadius: "50%", padding: 2,
          border: "1.5px solid #fff",
          width: 16, height: 16,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon name="accessibility" size={9} color="#fff" stroke={2.4} />
        </span>
      )}
      {c.here && (
        <span style={{
          position: "absolute", top: -16, left: "50%", transform: "translateX(-50%)",
          fontSize: 8, fontWeight: 800, letterSpacing: ".08em",
          color: "var(--obb-graphite)", textTransform: "uppercase",
          background: "#fff", padding: "1px 4px", borderRadius: 3,
          border: "1px solid var(--obb-line)",
          whiteSpace: "nowrap",
        }}>HIER</span>
      )}
    </div>
  );
}

// ─── Train ends — visual labels for "Wien ←" / "Salzburg →" orientation
function TrainOrientation() {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between",
      fontSize: 9, fontWeight: 600,
      color: "var(--obb-silver)", letterSpacing: ".04em",
      marginTop: 6, padding: "0 2px",
    }}>
      <span>← Lokomotive</span>
      <span>Fahrtrichtung →</span>
    </div>
  );
}

Object.assign(window, { LiveDot, FreshnessPill, CoachDiagram, CoachBlock, TrainOrientation });
