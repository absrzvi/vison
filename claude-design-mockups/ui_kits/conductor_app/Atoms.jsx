// Atoms — small reusable bits used across screens

// ─── Section micro-label ──────────────────────────────────────────
function SLabel({ children, style }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 700, letterSpacing: ".15em",
      color: "var(--obb-text-on-dark-4)",
      textTransform: "uppercase",
      margin: "10px 2px 6px",
      ...style,
    }}>{children}</div>
  );
}

// ─── Status bar / phone chrome ────────────────────────────────────
function StatusBar({ time, label }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between",
      padding: "0 6px 10px",
      fontSize: 10, color: "var(--obb-text-on-dark-4)",
      fontVariantNumeric: "tabular-nums",
    }}>
      <span>{time}</span>
      <span>{label}</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
        <Icon name="signal" size={10} stroke={2.5} /> 5G
      </span>
    </div>
  );
}

// ─── ÖBB-blue app header ──────────────────────────────────────────
function AppHeader({ trainId, route, time, conductor }) {
  return (
    <div style={{
      background: "linear-gradient(135deg, var(--obb-blue) 0%, var(--obb-blue-mid) 100%)",
      borderRadius: 18,
      padding: "13px 15px",
      marginBottom: 10,
      display: "flex", justifyContent: "space-between", alignItems: "center",
      boxShadow: "0 4px 16px rgba(7,61,110,0.5), inset 0 1px 0 rgba(255,255,255,0.1)",
      position: "relative", overflow: "hidden",
    }}>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", lineHeight: 1 }}>{trainId}</div>
        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.55)", marginTop: 3 }}>{route}</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 22, fontWeight: 200, color: "#fff", letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums" }}>{time}</div>
        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.5)", marginTop: 3 }}>{conductor}</div>
      </div>
    </div>
  );
}

// ─── Alert banner ─────────────────────────────────────────────────
const BANNER_TONES = {
  critical: { bg: "rgba(226,0,42,0.10)", border: "rgba(226,0,42,0.4)", icon: "#E2002A",  pulse: true },
  warning:  { bg: "rgba(245,166,35,0.10)", border: "rgba(245,166,35,0.35)", icon: "#F5A623", pulse: true },
  info:     { bg: "rgba(74,158,255,0.10)", border: "rgba(74,158,255,0.3)", icon: "#4A9EFF", pulse: false },
  resolved: { bg: "rgba(34,197,94,0.10)", border: "rgba(34,197,94,0.3)", icon: "#22C55E", pulse: false },
};

function AlertBanner({ tone = "warning", iconName, title, sub, onClick }) {
  const t = BANNER_TONES[tone];
  return (
    <div onClick={onClick} style={{
      borderRadius: 14,
      padding: "10px 12px",
      marginBottom: 10,
      display: "flex", alignItems: "center", gap: 10,
      border: `1px solid ${t.border}`,
      background: t.bg,
      animation: t.pulse ? "rn-pulse 2.4s ease-in-out infinite" : undefined,
      cursor: onClick ? "pointer" : "default",
      position: "relative", overflow: "hidden",
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: 10,
        background: t.bg.replace("0.10", "0.18"),
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <Icon name={iconName} size={16} color={t.icon} stroke={2.5} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: tone === "resolved" ? t.icon : "var(--obb-text-on-dark-1)", lineHeight: 1.3 }}>{title}</div>
        {sub && <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-3)", marginTop: 2 }}>{sub}</div>}
      </div>
      {onClick && <Icon name="chevron-right" size={14} color="var(--obb-text-on-dark-4)" />}
    </div>
  );
}

// ─── Coach diagram ────────────────────────────────────────────────
function CoachDiagram({ coaches, selected, onSelect }) {
  return (
    <div style={{ display: "flex", gap: 3, marginBottom: 10 }}>
      {coaches.map(c => {
        const tone = c.pct >= 80 ? "red" : c.pct >= 55 ? "amber" : "green";
        const isSel = selected === c.num;
        const tones = {
          green: { bg: "rgba(0,168,118,0.10)", border: "rgba(0,168,118,0.3)", text: "#22C55E", bar: "#22C55E" },
          amber: { bg: "rgba(245,166,35,0.12)", border: "rgba(245,166,35,0.3)", text: "#F5A623", bar: "#F5A623" },
          red:   { bg: "rgba(226,0,42,0.10)",  border: "rgba(226,0,42,0.4)",  text: "#FF3B3B", bar: "#FF3B3B" },
        }[tone];
        return (
          <button
            key={c.num}
            onClick={() => onSelect && onSelect(c.num)}
            style={{
              flex: 1,
              borderRadius: 8, padding: "8px 2px", textAlign: "center",
              background: tones.bg,
              border: `1px solid ${tones.border}`,
              boxShadow: isSel ? `0 0 0 2px var(--obb-blue-bright), 0 0 12px rgba(26,111,191,0.3)` : "none",
              cursor: "pointer", color: tones.text,
              transition: "all .15s var(--ease-out)",
              fontFamily: "inherit",
            }}>
            <div style={{ fontSize: 7, color: "var(--obb-text-on-dark-4)", marginBottom: 3, fontWeight: 600 }}>{c.num}</div>
            <div style={{ fontSize: 11, fontWeight: 800, lineHeight: 1 }}>{c.pct}%</div>
            <div style={{ height: 3, borderRadius: 2, margin: "4px 3px 0", background: tones.bar, opacity: 0.55 }} />
          </button>
        );
      })}
    </div>
  );
}

// ─── Detail row + grid ───────────────────────────────────────────
function DetailRow({ label, value, tone }) {
  const colors = { red: "#FF3B3B", amber: "#F5A623", green: "#22C55E", blue: "#4A9EFF" };
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
      padding: "5px 0",
      borderBottom: "1px solid rgba(255,255,255,0.04)",
      fontSize: 11,
    }}>
      <span style={{ color: "var(--obb-text-on-dark-3)", whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ fontWeight: 700, color: tone ? colors[tone] : "var(--obb-text-on-dark-1)", whiteSpace: "nowrap", textAlign: "right" }}>{value}</span>
    </div>
  );
}

function MetricGrid({ metrics }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginTop: 8 }}>
      {metrics.map((m, i) => {
        const color = m.tone === "critical" ? "#FF3B3B" : m.tone === "warning" ? "#FF6B00" : m.tone === "ok" ? "#22C55E" : "var(--obb-text-on-dark-1)";
        return (
          <div key={i} style={{ background: "var(--obb-surface-3)", borderRadius: 6, padding: 8, textAlign: "center" }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: "var(--obb-text-on-dark-4)", textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 3 }}>{m.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color }}>{m.value}</div>
            <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-4)" }}>{m.sub}</div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Rack bar ─────────────────────────────────────────────────────
function RackBar({ label, pct }) {
  const tone = pct >= 80 ? "high" : pct >= 50 ? "mid" : "low";
  const fills = {
    low:  "linear-gradient(90deg, #22C55E, #00e0a0)",
    mid:  "linear-gradient(90deg, #F5A623, #ffc840)",
    high: "linear-gradient(90deg, #FF3B3B, #ff5566)",
  };
  const textColor = pct >= 80 ? "#FF3B3B" : pct >= 50 ? "#F5A623" : "#22C55E";
  return (
    <div style={{
      marginTop: 8, background: "var(--obb-surface-3)",
      borderRadius: 10, padding: "9px 12px",
      border: "1px solid var(--obb-border-dark)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--obb-text-on-dark-3)", marginBottom: 6, fontWeight: 600, gap: 8 }}>
        <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
        <span style={{ color: textColor, whiteSpace: "nowrap" }}>{pct}%</span>
      </div>
      <div style={{ height: 5, background: "var(--obb-surface-5)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`, borderRadius: 3,
          background: fills[tone],
          transition: "width .4s var(--ease-out)",
          boxShadow: tone === "high" ? "0 0 6px rgba(226,0,42,0.4)" : "none",
        }} />
      </div>
    </div>
  );
}

// ─── Button ───────────────────────────────────────────────────────
function Btn({ kind = "primary", children, onClick, full = true, style = {}, ...rest }) {
  const styles = {
    primary:   { background: "linear-gradient(135deg, var(--obb-red), #c0001f)", color: "#fff", boxShadow: "0 2px 10px rgba(226,0,42,0.3)" },
    secondary: { background: "var(--obb-surface-4)", color: "var(--obb-text-on-dark-2)", border: "1px solid var(--obb-border-bright)" },
    blue:      { background: "linear-gradient(135deg, var(--obb-blue-mid), var(--obb-blue))", color: "#fff", boxShadow: "0 2px 10px rgba(7,61,110,0.3)" },
    ghost:     { background: "transparent", color: "var(--obb-text-on-dark-2)", border: "1px solid var(--obb-border-bright)" },
  };
  return (
    <button onClick={onClick} style={{
      flex: full ? 1 : "0 0 auto",
      border: 0, borderRadius: 9,
      padding: "9px 12px",
      fontSize: 11, fontWeight: 700,
      cursor: "pointer", textAlign: "center", letterSpacing: ".02em",
      fontFamily: "inherit",
      ...styles[kind], ...style,
    }} {...rest}>{children}</button>
  );
}

Object.assign(window, {
  SLabel, StatusBar, AppHeader, AlertBanner, CoachDiagram, DetailRow, MetricGrid, RackBar, Btn,
  BANNER_TONES,
});
