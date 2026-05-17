// ScenarioControls — floating panel to switch between the 5 demo scenarios

function ScenarioControls({ current, setCurrent }) {
  const [open, setOpen] = React.useState(true);
  return (
    <div style={{
      position: "fixed", top: 18, right: 18,
      background: "rgba(20,24,32,0.92)",
      border: "1px solid var(--obb-border-bright)",
      borderRadius: 14, padding: 6,
      boxShadow: "0 20px 40px rgba(0,0,0,0.4)",
      backdropFilter: "blur(8px)",
      WebkitBackdropFilter: "blur(8px)",
      zIndex: 100,
      maxWidth: 220,
    }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        width: "100%", background: "transparent", border: 0, color: "var(--obb-text-on-dark-3)",
        padding: "4px 8px", cursor: "pointer", fontFamily: "inherit",
        fontSize: 10, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase",
      }}>
        <span>Demo · Scenarios</span>
        <Icon name={open ? "chevron-down" : "chevron-right"} size={12} />
      </button>
      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
          {window.SCENARIO_ORDER.map((key, i) => {
            const s = window.SCENARIOS[key];
            const active = current === key;
            return (
              <button
                key={key}
                onClick={() => setCurrent(key)}
                style={{
                  border: 0, borderRadius: 10,
                  padding: "8px 10px", textAlign: "left",
                  background: active ? "var(--obb-red)" : "var(--obb-surface-3)",
                  color: active ? "#fff" : "var(--obb-text-on-dark-2)",
                  fontSize: 11, fontWeight: 600, cursor: "pointer",
                  fontFamily: "inherit",
                  display: "flex", alignItems: "center", gap: 8,
                  boxShadow: active ? "0 2px 8px rgba(226,0,42,0.4)" : "none",
                }}>
                <span style={{
                  width: 18, height: 18, borderRadius: "50%",
                  background: active ? "rgba(255,255,255,0.18)" : "var(--obb-surface-1)",
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, fontWeight: 800,
                  color: active ? "#fff" : "var(--obb-text-on-dark-3)",
                  flexShrink: 0,
                }}>{i + 1}</span>
                {s.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { ScenarioControls });
