// PhoneFrame — the 300×~640 phone bezel with status bar + app header

function PhoneFrame({ s, children, tab, setTab, badges }) {
  return (
    <div style={{ position: "relative", width: 320 }}>
      {/* side buttons */}
      <span style={{ position: "absolute", left: -4, top: 96, width: 4, height: 32, background: "#3A424F", borderRadius: "2px 0 0 2px", boxShadow: "0 40px 0 #3A424F, 0 80px 0 #3A424F" }} />
      <span style={{ position: "absolute", right: -4, top: 128, width: 4, height: 48, background: "#3A424F", borderRadius: "0 2px 2px 0" }} />

      <div style={{
        width: 320,
        background: "linear-gradient(160deg, var(--obb-surface-2) 0%, var(--obb-surface-1) 100%)",
        borderRadius: 42, border: "6px solid #3A424F", padding: "14px 12px 18px",
        boxShadow: "0 0 0 1px #2A303C, 0 4px 8px rgba(0,0,0,0.4), 0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
        overflow: "hidden", position: "relative",
      }}>
        {/* dynamic island */}
        <div style={{
          width: 96, height: 26, background: "#000", borderRadius: 13,
          margin: "0 auto 10px",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#111", border: "1px solid #222" }} />
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#1a1a1a" }} />
        </div>

        <StatusBar time={s.time} label="RJ 561 · K. Müller" />

        <AppHeader trainId="RJ 561" route="Wien Hbf → Salzburg Hbf" time={s.time} conductor={s.nextStop} />

        <div style={{
          maxHeight: 560, overflowY: "auto", overflowX: "hidden",
          paddingRight: 2, marginRight: -2,
        }}>
          {children}
        </div>

        <BottomNav tab={tab} setTab={setTab} badges={badges} />
      </div>
    </div>
  );
}

Object.assign(window, { PhoneFrame });
