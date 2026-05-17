// PhoneShell — iPhone bezel hosting the captive portal column

function PhoneShell({ children }) {
  return (
    <div style={{ position: "relative", width: 390 }}>
      <span style={{ position: "absolute", left: -4, top: 96, width: 4, height: 32, background: "#3A424F", borderRadius: "2px 0 0 2px", boxShadow: "0 40px 0 #3A424F, 0 80px 0 #3A424F" }} />
      <span style={{ position: "absolute", right: -4, top: 128, width: 4, height: 48, background: "#3A424F", borderRadius: "0 2px 2px 0" }} />

      <div style={{
        width: 390,
        background: "#fff",
        borderRadius: 48,
        border: "8px solid #14161B",
        boxShadow: "0 0 0 1px #2A303C, 0 4px 8px rgba(0,0,0,0.3), 0 30px 80px rgba(0,0,0,0.45)",
        overflow: "hidden", position: "relative",
      }}>
        {/* dynamic island */}
        <div style={{
          width: 110, height: 30, background: "#000", borderRadius: 15,
          position: "absolute", top: 10, left: "50%", transform: "translateX(-50%)",
          zIndex: 10,
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#111", border: "1px solid #222" }} />
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#1a1a1a" }} />
        </div>

        {/* status bar */}
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, zIndex: 5,
          display: "flex", justifyContent: "space-between",
          padding: "16px 24px 0",
          fontSize: 13, fontWeight: 600, color: "#000",
          fontVariantNumeric: "tabular-nums",
        }}>
          <span>12:15</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <Icon name="wifi" size={14} color="#000" stroke={2.4} /> LTE
          </span>
        </div>

        {/* CNA system chrome */}
        <div style={{
          marginTop: 44,
          padding: "8px 16px",
          background: "#F4F4F4",
          borderBottom: "1px solid #E5E5E5",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: 12, color: "var(--obb-graphite)",
        }}>
          <span style={{ fontWeight: 500 }}>WLAN-Anmeldung · railnet.oebb.at</span>
          <span style={{ color: "var(--obb-red)", fontWeight: 600 }}>Abbrechen</span>
        </div>

        {/* portal content */}
        <div style={{ background: "#fff", maxHeight: 700, overflowY: "auto" }}>
          {children}
        </div>

        {/* home indicator */}
        <div style={{
          padding: "8px 0 10px",
          display: "flex", justifyContent: "center",
        }}>
          <span style={{ width: 130, height: 4, borderRadius: 999, background: "rgba(0,0,0,.25)" }} />
        </div>
      </div>
    </div>
  );
}

window.PhoneShell = PhoneShell;
