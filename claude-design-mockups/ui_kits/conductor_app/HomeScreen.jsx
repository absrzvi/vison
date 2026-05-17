// Screens — each tab renders contextually based on current scenario

// ─── HOME SCREEN ──────────────────────────────────────────────────
function HomeScreen({ s, go, paSent, sendPa, dismissed, dismiss }) {
  return (
    <>
      {s.activeBanner && (
        <AlertBanner {...s.activeBanner} onClick={() => go(s.label === "Vestibule alert" ? "train" : s.label === "Unattended bag" ? "train" : "alerts")} />
      )}

      <SLabel>Coach Occupancy</SLabel>
      <CoachSection s={s} />

      <SLabel>Active Alerts</SLabel>
      <AlertList alerts={s.alerts.filter(a => !dismissed.has(a.title))} dismiss={dismiss} compact />

      {s.alerts.length > 0 && (
        <button onClick={() => go("alerts")} style={{
          width: "100%", marginTop: 6,
          background: "transparent", border: "1px solid var(--obb-border-bright)",
          borderRadius: 10, padding: "8px 10px",
          color: "var(--obb-text-on-dark-2)", fontSize: 11, fontWeight: 600,
          cursor: "pointer", fontFamily: "inherit",
        }}>View all alerts ›</button>
      )}

      <SLabel style={{ marginTop: 16 }}>Diagnostics Agent</SLabel>
      <ChatPreview onOpen={() => go("chat")} />
    </>
  );
}

// ─── Coach diagram + detail block, with selection state ──────────
function CoachSection({ s }) {
  const [sel, setSel] = React.useState(s.selectedCoach);
  const c = s.coaches.find(x => x.num === sel) || s.coaches[0];
  return (
    <div style={{
      background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
      borderRadius: 16, padding: 12, marginBottom: 10,
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
    }}>
      <CoachDiagram coaches={s.coaches} selected={sel} onSelect={setSel} />
      <div style={{ background: "var(--obb-surface-3)", borderRadius: 12, padding: "10px 12px", border: "1px solid var(--obb-border-dark)" }}>
        <DetailRow label="Coach selected"  value={`Coach ${c.num}`} tone="blue" />
        <DetailRow label="Occupancy"       value={`${c.pct}%`} tone={c.pct >= 80 ? "red" : c.pct >= 55 ? "amber" : "green"} />
        {s.metrics && sel === s.selectedCoach && <MetricGrid metrics={s.metrics} />}
      </div>
      {s.rackPct != null && <RackBar label={`Rack occupancy — Coach ${c.num}`} pct={s.rackPct} />}
    </div>
  );
}

// ─── Alert list (reused on Home compact + Alerts full) ───────────
function AlertList({ alerts, dismiss, compact = false }) {
  if (!alerts.length) {
    return (
      <div style={{
        background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
        borderRadius: 16, padding: 24,
        textAlign: "center", color: "var(--obb-text-on-dark-3)", fontSize: 11,
      }}>
        <Icon name="check-circle-2" size={28} color="#22C55E" style={{ marginBottom: 8 }} />
        <div>All clear. No active alerts on this train.</div>
      </div>
    );
  }
  return (
    <div style={{
      background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
      borderRadius: 16, padding: 10, marginBottom: 10,
      display: "flex", flexDirection: "column", gap: 6,
    }}>
      {alerts.slice(0, compact ? 3 : alerts.length).map((a, i) => <AlertRow key={a.title + i} a={a} dismiss={dismiss} />)}
    </div>
  );
}

const ALERT_STYLE = {
  fire:    { color: "#FF3B3B", bg: "rgba(255,59,59,0.08)",   border: "rgba(255,59,59,0.4)",   icon: "flame" },
  high:    { color: "#FF6B00", bg: "rgba(255,107,0,0.08)",   border: "#FF6B00", icon: "construction" },
  medium:  { color: "#F5A623", bg: "rgba(245,166,35,0.08)",  border: "#F5A623", icon: "alert-triangle" },
  warning: { color: "#F5A623", bg: "var(--obb-amber-dim)",   border: "#F5A623", icon: "package" },
  fault:   { color: "#7C52D6", bg: "var(--obb-purple-dim)",  border: "#7C52D6", icon: "thermometer" },
  info:    { color: "#4A9EFF", bg: "rgba(74,158,255,0.08)",  border: "#4A9EFF", icon: "info" },
};

function AlertRow({ a, dismiss }) {
  const style = ALERT_STYLE[a.type] || ALERT_STYLE.info;
  const isFire = a.type === "fire";
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      background: isFire ? style.bg : "var(--obb-surface-3)",
      borderRadius: 11,
      padding: "9px 10px",
      borderLeft: `2.5px solid ${style.border}`,
      border: isFire ? `1px solid ${style.border}` : `1px solid var(--obb-border-dark)`,
      borderLeft: `2.5px solid ${style.border}`,
      animation: isFire ? "rn-pulse-strong 1.4s ease-in-out infinite" : undefined,
    }}>
      <div style={{
        width: 30, height: 30, borderRadius: 8,
        background: style.bg,
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        <Icon name={a.iconName || style.icon} size={14} color={style.color} stroke={2.5} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: isFire ? style.color : "var(--obb-text-on-dark-1)" }}>{a.title}</div>
        <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-3)", marginTop: 2 }}>{a.sub}</div>
      </div>
      <div style={{ fontSize: 9, color: isFire ? style.color : "var(--obb-text-on-dark-4)", whiteSpace: "nowrap", paddingTop: 2, flexShrink: 0, fontWeight: isFire ? 700 : 500 }}>{a.when}</div>
      {dismiss && !isFire && (
        <button onClick={() => dismiss(a.title)} aria-label="Dismiss" style={{
          background: "transparent", border: 0, color: "var(--obb-text-on-dark-4)",
          cursor: "pointer", padding: 2, marginLeft: -4,
        }}>
          <Icon name="x" size={14} />
        </button>
      )}
    </div>
  );
}

// ─── Chat preview card on Home ────────────────────────────────────
function ChatPreview({ onOpen }) {
  return (
    <div onClick={onOpen} style={{
      background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
      borderRadius: 16, padding: 12, marginBottom: 10, cursor: "pointer",
    }}>
      <div style={{
        background: "var(--obb-surface-4)", borderRadius: "11px 11px 2px 11px",
        padding: "9px 12px", fontSize: 11, color: "var(--obb-text-on-dark-3)",
        marginBottom: 8, marginLeft: 24,
      }}>What's wrong with the HVAC in coach 3?</div>
      <div style={{
        background: "linear-gradient(135deg, rgba(7,61,110,0.4), rgba(10,82,152,0.25))",
        border: "1px solid rgba(10,82,152,0.3)",
        borderRadius: "2px 11px 11px 11px",
        padding: "9px 12px", fontSize: 11, color: "var(--obb-text-on-dark-1)",
        lineHeight: 1.6, marginRight: 24,
      }}>
        <div style={{ fontSize: 8, fontWeight: 800, letterSpacing: ".1em", color: "var(--obb-blue-accent)", marginBottom: 5, textTransform: "uppercase" }}>Diagnostics AI</div>
        Recirculation fan fault (0x3A12) — triggered 11 min ago. Pattern seen twice in 14 days. Likely bearing wear. Not safety‑critical now; flag for maintenance at Salzburg.
      </div>
    </div>
  );
}

Object.assign(window, { HomeScreen, AlertList, AlertRow, ChatPreview });
