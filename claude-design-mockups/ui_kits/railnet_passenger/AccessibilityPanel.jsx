// AccessibilityPanel — PRM space status + ramp loop

function AccessibilityPanel({ access }) {
  if (!access) return null;
  const isFree = access.tone === "free";
  const accent = isFree ? "#1F6BC9" : "#C9871F";
  const bg = isFree ? "rgba(74,158,255,0.07)" : "rgba(245,166,35,0.07)";
  const border = isFree ? "rgba(74,158,255,0.35)" : "rgba(245,166,35,0.4)";

  return (
    <div style={{
      background: bg,
      border: `1px solid ${border}`,
      borderRadius: 10,
      padding: "12px 14px",
      display: "flex",
      gap: 12,
      alignItems: "flex-start",
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: "#fff",
        border: `1px solid ${border}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <Icon name="accessibility" size={20} color={accent} stroke={2.4} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{
          fontSize: 14, fontWeight: 700,
          color: "var(--obb-ink)", lineHeight: 1.25,
          letterSpacing: "-.01em",
        }}>{access.status}</div>
        <div style={{ fontSize: 12, color: "var(--obb-graphite)", lineHeight: 1.4, marginTop: 3 }}>{access.detail}</div>

        {access.ramp && (
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            marginTop: 8, padding: "4px 10px 4px 8px",
            borderRadius: 999,
            background: access.ramp.state === "ready" ? "rgba(34,197,94,0.12)" : "rgba(74,158,255,0.10)",
            border: `1px solid ${access.ramp.state === "ready" ? "rgba(34,197,94,0.35)" : "rgba(74,158,255,0.25)"}`,
            fontSize: 11, fontWeight: 600,
            color: access.ramp.state === "ready" ? "#1F8A4C" : "#1F6BC9",
            animation: access.ramp.state === "ready" ? "rn-rise .35s var(--ease-out) both" : "none",
          }}>
            {access.ramp.state === "ready"
              ? <Icon name="check" size={11} stroke={3} />
              : <RampLoader />}
            {access.ramp.text}
          </div>
        )}

        {access.action && (
          <div style={{
            marginTop: 8,
            fontSize: 12, fontWeight: 600,
            color: accent,
            display: "inline-flex", alignItems: "center", gap: 5,
          }}>
            <Icon name="users" size={12} stroke={2.4} /> {access.action}
          </div>
        )}

        {access.conradAlert && (
          <div style={{
            marginTop: 8,
            fontSize: 10, color: "var(--obb-silver)",
            fontStyle: "italic", lineHeight: 1.4,
          }}>
            Der Zugbegleiter wurde automatisch informiert.
          </div>
        )}
      </div>
    </div>
  );
}

function RampLoader() {
  return (
    <span style={{
      width: 10, height: 10,
      borderRadius: "50%",
      border: "1.5px solid rgba(74,158,255,0.3)",
      borderTopColor: "#1F6BC9",
      display: "inline-block",
      animation: "rn-spin 1s linear infinite",
    }} />
  );
}

window.AccessibilityPanel = AccessibilityPanel;
