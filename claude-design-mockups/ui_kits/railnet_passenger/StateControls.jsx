// StateControls — sits beside the phone, not floating, so it never overlaps

function StateControls({ current, setCurrent }) {
  const groups = [
    { title: "Allgemein — Petra",          keys: ["mixed", "directed", "full", "mid_journey", "luggage_steer"] },
    { title: "Barrierefrei — Hanna",       keys: ["access_free", "access_occupied", "ramp_ready"] },
    { title: "Fallback",                   keys: ["stale", "no_data"] },
  ];
  const meta = window.STATE_META[current];

  return (
    <aside style={{
      width: 280, flexShrink: 0,
      background: "#fff",
      border: "1px solid var(--obb-line)",
      borderRadius: 16,
      boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
      overflow: "hidden",
      alignSelf: "stretch",
      maxHeight: 830,
      display: "flex", flexDirection: "column",
    }}>
      <div style={{
        padding: "14px 16px 12px",
        background: "linear-gradient(180deg, #fff 0%, var(--obb-bg) 100%)",
        borderBottom: "1px solid var(--obb-line)",
      }}>
        <div style={{
          fontSize: 10, fontWeight: 800, letterSpacing: ".1em",
          color: "var(--obb-silver)", textTransform: "uppercase",
        }}>Demo Steuerung</div>
        <div style={{
          fontSize: 14, fontWeight: 700, color: "var(--obb-ink)",
          letterSpacing: "-.01em", marginTop: 2,
        }}>{meta.label}</div>
        <div style={{
          fontSize: 11, color: "var(--obb-graphite)", marginTop: 3,
          fontFamily: "var(--font-mono)",
        }}>{meta.uc}</div>
      </div>

      <div style={{ padding: "10px 10px 12px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
        {groups.map(g => (
          <div key={g.title}>
            <div style={{
              fontSize: 9, fontWeight: 800, letterSpacing: ".1em",
              color: "var(--obb-silver)", textTransform: "uppercase",
              padding: "4px 4px 6px",
            }}>{g.title}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {g.keys.map(k => {
                const m = window.STATE_META[k];
                const active = current === k;
                return (
                  <button key={k}
                          onClick={() => setCurrent(k)}
                          style={{
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            padding: "9px 11px",
                            background: active ? "var(--obb-red)" : "#fff",
                            border: `1px solid ${active ? "var(--obb-red)" : "var(--obb-line)"}`,
                            borderRadius: 9,
                            color: active ? "#fff" : "var(--obb-body)",
                            fontFamily: "inherit",
                            fontSize: 12, fontWeight: 600,
                            cursor: "pointer", textAlign: "left",
                            boxShadow: active ? "0 2px 8px rgba(226,0,42,.3)" : "none",
                            transition: "all .12s var(--ease-out)",
                          }}>
                    <span>{m.label}</span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, letterSpacing: ".04em",
                      color: active ? "rgba(255,255,255,.7)" : "var(--obb-silver)",
                      fontVariantNumeric: "tabular-nums",
                      fontFamily: "var(--font-mono)",
                    }}>{m.uc}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

window.StateControls = StateControls;
