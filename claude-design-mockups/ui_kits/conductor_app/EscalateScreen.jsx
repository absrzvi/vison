// EscalateScreen — categorised form + inbox tab

const ESC_CATEGORIES_OPS = [
  { key: "medical", iconName: "stethoscope",   label: "Medical emergency",   route: "Claudia" },
  { key: "disrupt", iconName: "alert-octagon", label: "Disruptive passenger", route: "Claudia" },
  { key: "crowd",   iconName: "users",         label: "Overcrowding",        route: "Claudia" },
  { key: "access",  iconName: "accessibility", label: "Accessibility assist", route: "Claudia" },
];
const ESC_CATEGORIES_TECH = [
  { key: "door",    iconName: "door-closed",   label: "Door fault",          route: "Roland" },
  { key: "hvac",    iconName: "thermometer",   label: "HVAC / temperature",  route: "Roland" },
];

function EscalateScreen({ s, openCount, addEscalation, escalations }) {
  const [view, setView] = React.useState("form"); // form | inbox
  return (
    <>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        <SubTab active={view === "form"}  onClick={() => setView("form")}>Raise</SubTab>
        <SubTab active={view === "inbox"} onClick={() => setView("inbox")}>
          My Escalations <span style={{ marginLeft: 4, color: "var(--obb-text-on-dark-4)" }}>{openCount}</span>
        </SubTab>
      </div>
      {view === "form" ? <EscForm scenario={s} onSubmit={addEscalation} setView={setView} /> : <EscInbox items={escalations} />}
    </>
  );
}

function SubTab({ active, onClick, children }) {
  return (
    <button onClick={onClick} style={{
      flex: 1, background: active ? "var(--obb-surface-3)" : "transparent",
      border: `1px solid ${active ? "var(--obb-border-bright)" : "var(--obb-border-dark)"}`,
      borderRadius: 10, padding: "9px 8px",
      color: active ? "var(--obb-text-on-dark-1)" : "var(--obb-text-on-dark-3)",
      fontSize: 11, fontWeight: 700, cursor: "pointer",
      fontFamily: "inherit",
    }}>{children}</button>
  );
}

function EscForm({ scenario, onSubmit, setView }) {
  const [cat, setCat] = React.useState("medical");
  const [coach, setCoach] = React.useState(`Coach ${scenario.selectedCoach}`);
  const [severity, setSeverity] = React.useState("urgent");
  const allCats = [...ESC_CATEGORIES_OPS, ...ESC_CATEGORIES_TECH];
  const selectedCat = allCats.find(c => c.key === cat);
  const route = selectedCat?.route || "Claudia";

  return (
    <div style={{ padding: "2px 2px 4px" }}>
      <FormLabel>Category</FormLabel>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
        <SectionLabel>Operational → Claudia</SectionLabel>
        {ESC_CATEGORIES_OPS.map(c => <CatBtn key={c.key} cat={c} selected={cat === c.key} onClick={() => setCat(c.key)} />)}
        <SectionLabel>Technical → Roland</SectionLabel>
        {ESC_CATEGORIES_TECH.map(c => <CatBtn key={c.key} cat={c} selected={cat === c.key} onClick={() => setCat(c.key)} />)}
      </div>

      <div style={{ marginBottom: 12 }}>
        <FormLabel>Location</FormLabel>
        <FormInput>
          <span>{coach}</span>
          <Icon name="chevron-down" size={12} color="var(--obb-text-on-dark-4)" />
        </FormInput>
      </div>

      <div style={{ marginBottom: 12 }}>
        <FormLabel>Severity</FormLabel>
        <div style={{ display: "flex", gap: 8 }}>
          <SevBtn kind="urgent"   selected={severity === "urgent"}   onClick={() => setSeverity("urgent")} />
          <SevBtn kind="advisory" selected={severity === "advisory"} onClick={() => setSeverity("advisory")} />
        </div>
      </div>

      <FormLabel center>Add voice note or text</FormLabel>
      <button style={{
        width: 56, height: 56, borderRadius: "50%",
        background: "#4A9EFF", border: 0, cursor: "pointer",
        display: "flex", alignItems: "center", justifyContent: "center",
        margin: "0 auto 14px", boxShadow: "0 0 0 6px rgba(74,158,255,0.15)",
      }}>
        <Icon name="mic" size={22} color="#fff" stroke={2.2} />
      </button>

      <div style={{
        background: "rgba(74,158,255,0.06)", border: "1px solid rgba(74,158,255,0.2)",
        borderRadius: 8, padding: "10px 12px", fontSize: 11,
        color: "var(--obb-text-on-dark-3)", marginBottom: 14,
      }}>
        This escalation will go to <strong style={{ color: "#4A9EFF" }}>{route} — Vienna Control</strong><br/>
        <span style={{ fontSize: 10, color: "var(--obb-text-on-dark-4)" }}>
          {route === "Claudia" ? "Operational issues route to the Control Centre for live coordination." : "Technical faults route to fleet maintenance for remote diagnosis."}
        </span>
      </div>

      <button onClick={() => { onSubmit({ category: selectedCat, coach, severity }); setView("inbox"); }} style={{
        width: "100%", background: "#4A9EFF", border: 0, borderRadius: 10,
        padding: 14, fontSize: 14, fontWeight: 700, color: "#fff",
        cursor: "pointer", fontFamily: "inherit",
      }}>Submit Escalation</button>
    </div>
  );
}

function CatBtn({ cat, selected, onClick }) {
  return (
    <button onClick={onClick} style={{
      background: selected ? "rgba(74,158,255,0.08)" : "var(--obb-surface-3)",
      border: `1px solid ${selected ? "#4A9EFF" : "var(--obb-border-dark)"}`,
      borderRadius: 8, padding: "10px 8px", textAlign: "center", cursor: "pointer",
      transition: "all .15s var(--ease-out)",
      fontFamily: "inherit",
    }}>
      <Icon name={cat.iconName} size={18} color={selected ? "#4A9EFF" : "var(--obb-text-on-dark-2)"} stroke={2.2} style={{ marginBottom: 4 }} />
      <div style={{ fontSize: 10, fontWeight: 600, color: "var(--obb-text-on-dark-1)" }}>{cat.label}</div>
      <div style={{ fontSize: 9, color: "var(--obb-text-on-dark-4)", marginTop: 2 }}>→ {cat.route}</div>
    </button>
  );
}

function SevBtn({ kind, selected, onClick }) {
  const tones = {
    urgent:   { color: "#FF3B3B", label: "Urgent",   icon: "alert-circle" },
    advisory: { color: "#4A9EFF", label: "Advisory", icon: "info" },
  }[kind];
  return (
    <button onClick={onClick} style={{
      flex: 1, padding: "9px 8px", borderRadius: 8,
      border: `1px solid ${selected ? tones.color : "var(--obb-border-dark)"}`,
      background: selected ? `${tones.color}18` : "var(--obb-surface-3)",
      color: selected ? tones.color : "var(--obb-text-on-dark-2)",
      fontSize: 11, fontWeight: 700, cursor: "pointer",
      display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
      fontFamily: "inherit",
    }}>
      <Icon name={tones.icon} size={12} stroke={2.4} /> {tones.label}
    </button>
  );
}

function FormLabel({ children, center }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 700,
      color: "var(--obb-text-on-dark-4)",
      textTransform: "uppercase", letterSpacing: ".08em",
      marginBottom: 6, textAlign: center ? "center" : "left",
    }}>{children}</div>
  );
}
function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 700,
      color: "var(--obb-text-on-dark-4)", textTransform: "uppercase", letterSpacing: ".1em",
      gridColumn: "1 / -1", marginTop: 4,
    }}>{children}</div>
  );
}
function FormInput({ children }) {
  return (
    <div style={{
      width: "100%", background: "var(--obb-surface-3)",
      border: "1px solid var(--obb-border-dark)", borderRadius: 8,
      padding: "10px 12px", fontSize: 12, color: "var(--obb-text-on-dark-1)",
      display: "flex", justifyContent: "space-between", alignItems: "center",
    }}>{children}</div>
  );
}

// ─── Inbox ────────────────────────────────────────────────────────
function EscInbox({ items }) {
  if (!items.length) {
    return (
      <div style={{
        background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
        borderRadius: 16, padding: 28, textAlign: "center",
        color: "var(--obb-text-on-dark-3)", fontSize: 12,
      }}>
        <Icon name="inbox" size={28} color="var(--obb-text-on-dark-4)" style={{ marginBottom: 8 }} />
        <div>No escalations yet.<br/>Raise one via the form.</div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {items.map((it, i) => <InboxItem key={i} it={it} />)}
    </div>
  );
}

function InboxItem({ it }) {
  const pill = {
    new:  { bg: "rgba(255,59,59,0.15)", color: "#FF3B3B", label: "New" },
    ack:  { bg: "rgba(245,166,35,0.15)", color: "#F5A623", label: "Ack'd" },
    done: { bg: "rgba(34,197,94,0.15)",  color: "#22C55E", label: "Resolved" },
  }[it.status];
  const border = it.status === "new" ? "#FF3B3B" : it.status === "ack" ? "#F5A623" : "var(--obb-border-bright)";
  return (
    <div style={{
      background: "var(--obb-surface-3)", borderRadius: 10, padding: 12,
      borderLeft: `3px solid ${border}`,
      opacity: it.status === "done" ? 0.6 : 1,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{
            fontSize: 12, fontWeight: 700,
            color: "var(--obb-text-on-dark-1)",
            textDecoration: it.status === "done" ? "line-through" : "none",
          }}>{it.category.label}</div>
          <div style={{ fontSize: 11, color: "var(--obb-text-on-dark-3)", marginTop: 2 }}>
            {it.coach} · {it.severity === "urgent" ? "Urgent" : "Advisory"} · {it.category.route}
          </div>
        </div>
        <span style={{
          fontSize: 9, fontWeight: 700,
          padding: "2px 7px", borderRadius: 10,
          textTransform: "uppercase", letterSpacing: ".05em",
          background: pill.bg, color: pill.color,
        }}>{pill.label}</span>
      </div>
      {it.note && (
        <div style={{
          marginTop: 8, padding: 8,
          background: "var(--obb-surface-1)", borderRadius: 6,
          fontSize: 11, color: "var(--obb-text-on-dark-2)", fontStyle: "italic",
        }}>"{it.note}"</div>
      )}
      <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-4)", marginTop: 6 }}>{it.timestamp} · {it.ref}</div>
    </div>
  );
}

Object.assign(window, { EscalateScreen });
